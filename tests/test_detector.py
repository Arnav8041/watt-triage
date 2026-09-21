import pytest

from app import db
from app.main import app


def query(sql):
    with app.state.pool.connection() as conn:
        return conn.execute(sql).fetchall()


def test_seed_readings_writes_past_history_for_one_appliance_in_one_call(client):
    db.seed_readings(app.state.pool, "fridge", [100, 110, 120], interval_seconds=5)
    rows = query("SELECT watts, now() - recorded_at FROM reading ORDER BY recorded_at")
    assert [r[0] for r in rows] == [100, 110, 120]  # oldest first
    ages = [r[1].total_seconds() for r in rows]
    assert ages == sorted(ages, reverse=True)  # older = further back
    assert 4 < ages[1] - ages[2] < 6  # 5s apart
    assert all(a > 0 for a in ages)  # all in the past


NORMAL = [100, 110] * 30  # mean 105, std dev 5


def post(client, watts, appliance="space_heater"):  # space heater is rated 1500 W
    assert client.post("/readings", json={"appliance_id": appliance, "watts": watts}).status_code == 202


def test_sustained_deviation_raises_a_statistical_candidate(client):
    db.seed_readings(app.state.pool, "space_heater", NORMAL)
    post(client, 500)
    post(client, 500)
    assert query("SELECT * FROM anomaly_candidate") == []  # two in a row isn't enough
    post(client, 500)
    rows = query(
        "SELECT appliance_id, watts, trigger, status, z_score, baseline_size, baseline_mean, baseline_stddev "
        "FROM anomaly_candidate"
    )
    # z = (500 - 105) / 5 = 79. Baseline is just the 60 seeded readings, no spikes
    assert rows == [("space_heater", 500, "statistical", "pending", pytest.approx(79), 60, pytest.approx(105), pytest.approx(5))]


def test_single_reading_blip_raises_nothing(client):
    db.seed_readings(app.state.pool, "space_heater", NORMAL)
    for watts in (500, 100, 100):  # one blip, then normal
        post(client, watts)
    assert query("SELECT * FROM anomaly_candidate") == []


def test_flat_history_raises_nothing_and_does_not_error(client):
    db.seed_readings(app.state.pool, "space_heater", [100.0] * 60)  # std dev is 0
    for _ in range(3):
        post(client, 500)
    assert query("SELECT * FROM anomaly_candidate") == []


def test_too_little_history_suppresses_statistical_but_not_rated_breach(client):
    db.seed_readings(app.state.pool, "space_heater", [100, 110, 100, 110, 100])  # 5 readings
    for _ in range(3):
        post(client, 1000)  # odd, but under the 1500 W rating
    assert query("SELECT * FROM anomaly_candidate") == []
    post(client, 2000)  # over the rating, still raises
    assert query("SELECT trigger FROM anomaly_candidate") == [("rated_breach",)]


def test_only_one_statistical_candidate_is_pending_per_appliance(client):
    db.seed_readings(app.state.pool, "space_heater", NORMAL)
    for _ in range(6):  # keeps going after it first qualified
        post(client, 500)
    assert query("SELECT trigger FROM anomaly_candidate") == [("statistical",)]


def test_rated_breach_still_raises_while_a_statistical_candidate_is_pending(client):
    db.seed_readings(app.state.pool, "space_heater", NORMAL)
    for _ in range(3):
        post(client, 500)
    post(client, 2000)  # over the 1500 W rating
    triggers = sorted(r[0] for r in query("SELECT trigger FROM anomaly_candidate"))
    assert triggers == ["rated_breach", "statistical"]


def test_a_stale_pending_candidate_stops_blocking_new_ones(client):
    # left behind an hour ago, agent timeout is 30s
    with app.state.pool.connection() as conn:
        conn.execute(
            "INSERT INTO anomaly_candidate (appliance_id, watts, trigger, detected_at) "
            "VALUES ('space_heater', 500, 'statistical', now() - interval '1 hour')"
        )
    db.seed_readings(app.state.pool, "space_heater", NORMAL)
    for _ in range(3):
        post(client, 500)
    assert query("SELECT trigger FROM anomaly_candidate") == [("statistical",), ("statistical",)]


def test_persistence_and_threshold_come_from_environment_variables(client, monkeypatch):
    monkeypatch.setenv("DETECTOR_PERSISTENCE", "2")  # two in a row now
    monkeypatch.setenv("DETECTOR_Z_THRESHOLD", "100")  # z has to beat 100, this is 79
    db.seed_readings(app.state.pool, "space_heater", NORMAL)
    post(client, 500)
    post(client, 500)
    assert query("SELECT * FROM anomaly_candidate") == []
    monkeypatch.setenv("DETECTOR_Z_THRESHOLD", "5")  # first 500 is in the baseline now, so z is ~7.7
    post(client, 500)
    assert query("SELECT trigger FROM anomaly_candidate") == [("statistical",)]
