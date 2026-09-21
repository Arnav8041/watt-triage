import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch):
    # The tests wipe tables, so never run them against the real database.
    assert os.environ["TEST_DATABASE_URL"] != os.environ.get("DATABASE_URL")
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    with TestClient(app) as c:  # `with` runs startup, schema included
        with app.state.pool.connection() as conn:
            conn.execute("TRUNCATE reading, anomaly_candidate CASCADE")
        yield c
