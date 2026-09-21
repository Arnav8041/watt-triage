import os

import pytest
from fastapi.testclient import TestClient

from app import agent
from app.main import app
from tests.fakes import ScriptedClient


@pytest.fixture
def client(monkeypatch):
    # The tests wipe tables, so never run them against the real database.
    assert os.environ["TEST_DATABASE_URL"] != os.environ.get("DATABASE_URL")
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    with TestClient(app) as c:  # `with` runs startup, schema included
        with app.state.pool.connection() as conn:
            conn.execute("TRUNCATE reading, anomaly_candidate CASCADE")
        app.state.client = ScriptedClient()  # empty script: the model is "down", never the real API
        # ingest/detector tests should leave Candidates pending; agent tests call triage() themselves
        monkeypatch.setattr(agent, "triage", lambda *args: None)
        yield c
