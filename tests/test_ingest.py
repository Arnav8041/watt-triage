import pytest
from fastapi.testclient import TestClient

from app.main import app

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
    # Strict JSON has no infinity or NaN, but the server's parser accepts the bare tokens.
    r = client.post(
        "/readings",
        content='{"appliance_id": "fridge", "watts": %s}' % bad,
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 422
    assert query("SELECT * FROM reading") == []


def test_five_appliances_seeded_with_rated_wattage(client):
    assert dict(query("SELECT id, rated_watts FROM appliance")) == RATED_WATTS


def test_starting_twice_does_not_duplicate_appliances(client):
    with TestClient(app):  # a second startup against the same database
        assert len(query("SELECT * FROM appliance")) == 5


def test_missing_database_url_fails_at_startup(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        with TestClient(app):
            pass
