from app import simulator
from app.main import app


def test_reset_wipes_candidates_and_replants_baseline_readings(client):
    simulator.seed(app.state.pool)
    client.post("/admin/fire/washer-spin")  # leaves a pending Candidate behind

    r = client.post("/admin/reset")

    assert r.status_code == 200
    with app.state.pool.connection() as conn:
        assert conn.execute("SELECT count(*) FROM anomaly_candidate").fetchone()[0] == 0
    appliances = {a["id"]: a for a in client.get("/appliances").json()}
    assert all(a["latest_watts"] is not None for a in appliances.values())


def test_reset_clears_an_active_fire_cooldown(client):
    simulator.seed(app.state.pool)
    client.post("/admin/fire/washer-spin")  # starts the cooldown

    client.post("/admin/reset")
    r = client.post("/admin/fire/washer-spin")

    assert r.status_code == 202
