from app import db, simulator
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


def test_reset_does_not_clear_the_agent_run_budget(client):
    # /admin/reset is public and unauthenticated (ticket #15): if it cleared the budget too,
    # anyone could reset their own hourly spend cap on demand (ticket #16).
    db.reserve_agent_run(app.state.pool, budget=1)

    client.post("/admin/reset")

    assert db.agent_runs_this_hour(app.state.pool) == 1
