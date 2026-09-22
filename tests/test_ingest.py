import os
import threading
import time

import httpx2
import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import agent
from app.agent import triage as real_triage
from app.main import app
from tests.fakes import ScriptedClient, submit, tool_use

RATED_WATTS = {
    "fridge": 250,
    "water_heater": 4500,
    "space_heater": 1500,
    "washer": 1200,
    "ac_unit": 3500,
}


def query(sql):
    with app.state.pool.connection() as conn:
        return conn.execute(sql).fetchall()


def test_health(client):
    assert client.get("/health").status_code == 200


def test_valid_reading_is_stored(client):
    r = client.post("/readings", json={"appliance_id": "fridge", "watts": 120.5})
    assert r.status_code == 202
    assert query("SELECT appliance_id, watts FROM reading") == [("fridge", 120.5)]


def test_unknown_appliance_is_rejected(client):
    r = client.post("/readings", json={"appliance_id": "toaster", "watts": 100})
    assert r.status_code == 422
    assert "toaster" in r.json()["detail"]
    assert query("SELECT * FROM reading") == []


def test_negative_wattage_is_rejected(client):
    r = client.post("/readings", json={"appliance_id": "fridge", "watts": -5})
    assert r.status_code == 422
    assert query("SELECT * FROM reading") == []


@pytest.mark.parametrize("bad", ["Infinity", "-Infinity", "NaN"])
def test_non_finite_wattage_is_rejected(client, bad):
    # Strict JSON has no infinity or NaN, but the server's parser accepts them.
    r = client.post(
        "/readings",
        content='{"appliance_id": "fridge", "watts": %s}' % bad,
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 422
    assert query("SELECT * FROM reading") == []


def test_reading_above_rated_wattage_raises_a_rated_breach_candidate(client):
    # Space heater is rated 1500W. The table is empty, so this covers a cold start too.
    r = client.post("/readings", json={"appliance_id": "space_heater", "watts": 3180})
    assert r.status_code == 202
    rows = query("SELECT appliance_id, watts, trigger, status, detected_at FROM anomaly_candidate")
    assert len(rows) == 1
    appliance_id, watts, trigger, status, detected_at = rows[0]
    assert (appliance_id, watts, trigger, status) == ("space_heater", 3180, "rated_breach", "pending")
    assert detected_at is not None


@pytest.mark.parametrize("watts", [1500, 900])
def test_reading_at_or_below_rated_wattage_raises_no_candidate(client, watts):
    r = client.post("/readings", json={"appliance_id": "space_heater", "watts": watts})
    assert r.status_code == 202
    assert query("SELECT * FROM anomaly_candidate") == []
    assert len(query("SELECT * FROM reading")) == 1


def test_five_appliances_seeded_with_rated_wattage(client):
    assert dict(query("SELECT id, rated_watts FROM appliance")) == RATED_WATTS


def test_starting_twice_does_not_duplicate_appliances(client):
    with TestClient(app):  # a second startup on the same database
        assert len(query("SELECT * FROM appliance")) == 5


def test_missing_database_url_fails_at_startup(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        with TestClient(app):
            pass


def test_breach_reading_is_investigated_and_escalated_end_to_end(client, monkeypatch):
    monkeypatch.setattr(agent, "triage", real_triage)  # the client fixture switches it off
    # The fake model is confidently wrong: it says "resolve quietly, certain" about a Rated Breach.
    app.state.client = ScriptedClient(
        [tool_use("get_appliance_profile", appliance_id="space_heater")],
        [submit("resolve_quietly", "certain", "Just warming up.")],
    )

    r = client.post("/readings", json={"appliance_id": "space_heater", "watts": 3180})

    assert r.status_code == 202
    assert query("SELECT outcome, reasoning FROM triage_decision") == [("escalated", "Just warming up.")]
    assert query("SELECT status FROM anomaly_candidate") == [("decided",)]


class FrozenClient(ScriptedClient):
    """A model that hangs on its first call until the test lets it go."""

    def __init__(self, *replies):
        super().__init__(*replies)
        self.asked = threading.Event()
        self.release = threading.Event()

    def create(self, **kwargs):
        self.asked.set()
        self.release.wait(timeout=10)
        return super().create(**kwargs)


def test_ingest_responds_without_waiting_for_the_model(monkeypatch):
    # TestClient waits for background work, so this needs a real server on a real port.
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    server = uvicorn.Server(uvicorn.Config(app, port=0, log_level="warning"))
    thread = threading.Thread(target=server.run)
    thread.start()
    frozen = FrozenClient(
        [tool_use("get_appliance_profile", appliance_id="space_heater")],
        [submit("resolve_quietly", "certain")],
    )
    try:
        while not server.started:
            time.sleep(0.05)
        with app.state.pool.connection() as conn:
            conn.execute("TRUNCATE reading, anomaly_candidate CASCADE")
        app.state.client = frozen
        port = server.servers[0].sockets[0].getsockname()[1]

        # If ingest waited for the frozen model, this would time out after 3 seconds.
        r = httpx2.post(
            f"http://127.0.0.1:{port}/readings",
            json={"appliance_id": "space_heater", "watts": 3180},
            headers={"X-API-Key": os.environ["WRITE_API_KEY"]},
            timeout=3,
        )

        assert r.status_code == 202
        assert frozen.asked.wait(timeout=3)  # the agent did start, and is stuck on the model
        assert query("SELECT * FROM triage_decision") == []  # ...so there is no decision yet
        frozen.release.set()
        for _ in range(100):  # the decision appears once the model answers
            if query("SELECT outcome FROM triage_decision"):
                break
            time.sleep(0.05)
        assert query("SELECT outcome FROM triage_decision") == [("escalated",)]
    finally:
        frozen.release.set()
        server.should_exit = True
        thread.join()
