from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from app import db
from app.main import app
from tests.test_acknowledge import make_decision, row

# A whole hour, 10 hours ago: always older than the 2-hour window.
HOUR_A = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=10)
HOUR_B = HOUR_A + timedelta(hours=1)


def plant(appliance_id, when, watts_list):
    """Insert Readings at exact times: the first at `when`, then one minute apart."""
    with app.state.pool.connection() as conn:
        for i, watts in enumerate(watts_list):
            conn.execute(
                "INSERT INTO reading (appliance_id, watts, recorded_at) VALUES (%s, %s, %s)",
                (appliance_id, watts, when + timedelta(minutes=i)),
            )


def rollup_rows():
    with app.state.pool.connection() as conn:
        return conn.execute(
            "SELECT appliance_id, hour, min_watts, max_watts, avg_watts, sample_count "
            "FROM rollup ORDER BY appliance_id, hour"
        ).fetchall()


def reading_count():
    with app.state.pool.connection() as conn:
        return conn.execute("SELECT count(*) FROM reading").fetchone()[0]


def test_readings_become_one_row_per_appliance_per_hour_with_the_right_numbers(client):
    plant("fridge", HOUR_A, [100, 200, 300])  # hand-worked: min 100, max 300, avg 200, count 3
    plant("fridge", HOUR_B, [50, 150])  # min 50, max 150, avg 100, count 2
    plant("washer", HOUR_A, [400, 800])  # a different Appliance, same hour: min 400, max 800, avg 600, count 2

    db.rollup_old_readings(app.state.pool, retention_hours=2)

    assert rollup_rows() == [
        ("fridge", HOUR_A, 100, 300, 200, 3),
        ("fridge", HOUR_B, 50, 150, 100, 2),
        ("washer", HOUR_A, 400, 800, 600, 2),
    ]


def test_old_readings_are_deleted_and_newer_ones_are_untouched(client):
    plant("fridge", HOUR_A, [100, 200, 300])
    inside_window = datetime.now(timezone.utc) - timedelta(minutes=90)  # newer than the 2-hour window
    plant("fridge", inside_window, [120, 130])

    db.rollup_old_readings(app.state.pool, retention_hours=2)

    with app.state.pool.connection() as conn:
        left = conn.execute("SELECT watts FROM reading ORDER BY watts").fetchall()
    assert left == [(120,), (130,)]
    assert [row[1] for row in rollup_rows()] == [HOUR_A]  # the recent hour was not rolled up


def test_running_it_twice_changes_nothing_the_second_time(client):
    plant("fridge", HOUR_A, [100, 200, 300])
    plant("fridge", HOUR_B, [50, 150])
    db.rollup_old_readings(app.state.pool, retention_hours=2)
    after_first = rollup_rows()

    db.rollup_old_readings(app.state.pool, retention_hours=2)

    assert rollup_rows() == after_first  # same rows, same numbers, nothing doubled
    assert reading_count() == 0


def test_an_hour_that_already_has_a_row_is_overwritten_not_duplicated(client):
    with app.state.pool.connection() as conn:  # a stale summary for the same Appliance and hour
        conn.execute("INSERT INTO rollup VALUES ('fridge', %s, 1, 1, 1, 1)", (HOUR_A,))
    plant("fridge", HOUR_A, [100, 200, 300])

    db.rollup_old_readings(app.state.pool, retention_hours=2)  # without the upsert this hits a primary-key clash

    assert rollup_rows() == [("fridge", HOUR_A, 100, 300, 200, 3)]


def test_a_failure_part_way_leaves_the_data_unchanged(client):
    plant("fridge", HOUR_A, [100, 200, 300])
    with app.state.pool.connection() as conn:  # sabotage: any DELETE on reading now raises an error
        conn.execute(
            "CREATE FUNCTION fail_delete() RETURNS trigger LANGUAGE plpgsql AS "
            "$$ BEGIN RAISE EXCEPTION 'simulated crash'; END $$"
        )
        conn.execute("CREATE TRIGGER fail_delete BEFORE DELETE ON reading FOR EACH ROW EXECUTE FUNCTION fail_delete()")
    try:
        with pytest.raises(psycopg.errors.RaiseException):
            db.rollup_old_readings(app.state.pool, retention_hours=2)  # the delete raises, so the whole statement fails
    finally:
        with app.state.pool.connection() as conn:
            conn.execute("DROP TRIGGER fail_delete ON reading")
            conn.execute("DROP FUNCTION fail_delete()")

    assert rollup_rows() == []  # the summary was rolled back too
    assert reading_count() == 3


# the endpoint

def test_the_endpoint_uses_the_retention_window_from_the_environment(client, monkeypatch):
    plant("fridge", HOUR_A, [100, 200, 300])  # 10 hours old

    monkeypatch.delenv("RETENTION_HOURS", raising=False)  # so the 24-hour default applies: these are still inside it
    assert client.post("/admin/rollup").json() == {"rollup_rows": 0, "readings_deleted": 0}
    assert reading_count() == 3

    monkeypatch.setenv("RETENTION_HOURS", "2")
    response = client.post("/admin/rollup")

    assert response.status_code == 200
    assert response.json() == {"rollup_rows": 1, "readings_deleted": 3}
    assert reading_count() == 0


def test_a_decision_is_fully_readable_after_its_readings_are_rolled_up(client, monkeypatch):
    decision_id = make_decision()
    plant("space_heater", HOUR_A, [600, 700, 800])  # the Readings the decision was about
    before = row(decision_id)

    monkeypatch.setenv("RETENTION_HOURS", "2")
    client.post("/admin/rollup")

    assert reading_count() == 0  # the raw Readings really are gone
    assert row(decision_id) == before  # evidence, trace and reasoning are all still there


@pytest.mark.parametrize("bad", ["-1", "nan", "inf", "soon"])
def test_a_bad_retention_window_is_refused_and_nothing_is_deleted(client, monkeypatch, bad):
    plant("fridge", HOUR_A, [100, 200, 300])
    monkeypatch.setenv("RETENTION_HOURS", bad)

    with pytest.raises(ValueError):
        client.post("/admin/rollup")  # the test client re-raises the server's error

    assert reading_count() == 3
    assert rollup_rows() == []
