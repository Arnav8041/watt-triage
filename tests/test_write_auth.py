from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app

WRITE_ENDPOINTS = ["/readings", "/admin/rollup"]


def _body(path):
    return {"appliance_id": "fridge", "watts": 100} if path == "/readings" else None


def _reading_count():
    with app.state.pool.connection() as conn:
        return conn.execute("SELECT count(*) FROM reading").fetchone()[0]


def _plant_old_reading():
    """A Reading old enough that /admin/rollup would summarise and delete it, if it ran."""
    with app.state.pool.connection() as conn:
        conn.execute(
            "INSERT INTO reading (appliance_id, watts, recorded_at) VALUES ('fridge', 100, %s)",
            (datetime.now(timezone.utc) - timedelta(hours=48),),
        )


@pytest.mark.parametrize("path", WRITE_ENDPOINTS)
def test_missing_key_is_rejected_and_nothing_is_stored(client, path):
    _plant_old_reading()  # old enough for /admin/rollup to delete it, if it ran
    before = _reading_count()
    with TestClient(app) as anon:  # a second startup with no default header
        r = anon.post(path, json=_body(path))
        assert r.status_code == 401
        assert _reading_count() == before  # neither a new Reading nor a rollup deletion happened


@pytest.mark.parametrize("path", WRITE_ENDPOINTS)
def test_wrong_key_is_rejected_and_nothing_is_stored(client, path):
    _plant_old_reading()
    before = _reading_count()
    r = client.post(path, json=_body(path), headers={"X-API-Key": "not-the-real-key"})
    assert r.status_code == 401
    assert _reading_count() == before


@pytest.mark.parametrize("path", WRITE_ENDPOINTS)
def test_right_key_behaves_exactly_as_before(client, path):
    r = client.post(path, json=_body(path))
    assert r.status_code in (200, 202)


def test_the_key_is_never_echoed_back_in_the_401_body(client):
    r = client.post("/readings", json=_body("/readings"), headers={"X-API-Key": "not-the-real-key"})
    assert "not-the-real-key" not in r.text


@pytest.mark.parametrize("path", ["/health", "/appliances"])
def test_read_only_endpoints_work_with_no_key_at_all(path):
    with TestClient(app) as anon:  # no default header, and no WRITE_API_KEY override either
        assert anon.get(path).status_code == 200


def test_missing_write_api_key_fails_at_startup(monkeypatch):
    monkeypatch.delenv("WRITE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="WRITE_API_KEY"):
        with TestClient(app):
            pass
