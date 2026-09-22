from app import db, simulator
from app.main import app


def readings_for(appliance_id):
    with app.state.pool.connection() as conn:
        return [
            watts
            for (watts,) in conn.execute(
                "SELECT watts FROM reading WHERE appliance_id = %s ORDER BY recorded_at, id", (appliance_id,)
            )
        ]


def candidates_for(appliance_id):
    with app.state.pool.connection() as conn:
        return conn.execute(
            "SELECT trigger FROM anomaly_candidate WHERE appliance_id = %s", (appliance_id,)
        ).fetchall()


def test_fire_rejects_an_unknown_scenario(client):
    r = client.post("/admin/fire/toaster-meltdown")

    assert r.status_code == 404


def test_fire_posts_the_scenario_readings_and_raises_a_candidate(client):
    simulator.seed(app.state.pool)

    r = client.post("/admin/fire/washer-spin")

    assert r.status_code == 202
    assert len(readings_for("washer")) == simulator.SEED_HOURS * 3600 // simulator.SEED_INTERVAL_SECONDS + len(
        simulator.fire_readings("washer-spin")
    )
    candidates = candidates_for("washer")
    assert candidates
    assert all(trigger == "statistical" for (trigger,) in candidates)


def test_firing_twice_in_a_row_is_refused_while_the_cooldown_is_active(client):
    simulator.seed(app.state.pool)
    first = client.post("/admin/fire/washer-spin")

    second = client.post("/admin/fire/washer-spin")

    assert first.status_code == 202
    assert second.status_code == 409
    assert "detail" in second.json()


def test_firing_again_after_the_cooldown_clears_is_allowed(client):
    simulator.seed(app.state.pool)
    client.post("/admin/fire/washer-spin")
    app.state.fire_cooldown_until = 0.0  # simulate the window having elapsed

    r = client.post("/admin/fire/washer-spin")

    assert r.status_code == 202
