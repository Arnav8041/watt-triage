import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch):
    # The tests wipe tables, so refuse to run if they would point at the real database.
    assert os.environ["TEST_DATABASE_URL"] != os.environ.get("DATABASE_URL")
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    with TestClient(app) as c:  # `with` runs the app's startup, including the schema
        with app.state.pool.connection() as conn:
            conn.execute("TRUNCATE reading")
        yield c
