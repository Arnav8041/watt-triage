from app.main import app, cors_origins
from tests.test_acknowledge import make_decision
from tests.test_agent import make_candidate


def test_appliances_lists_all_five_with_rated_watts(client):
    r = client.get("/appliances")

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 5
    ids = {a["id"] for a in body}
    assert ids == {"fridge", "water_heater", "space_heater", "washer", "ac_unit"}
    fridge = next(a for a in body if a["id"] == "fridge")
    assert fridge["rated_watts"] == 250


def test_appliances_with_no_readings_have_a_null_latest_reading(client):
    fridge = next(a for a in client.get("/appliances").json() if a["id"] == "fridge")

    assert fridge["latest_watts"] is None
    assert fridge["latest_recorded_at"] is None


def test_appliances_show_the_newest_reading_not_the_first(client):
    client.post("/readings", json={"appliance_id": "fridge", "watts": 100})
    client.post("/readings", json={"appliance_id": "fridge", "watts": 180})

    fridge = next(a for a in client.get("/appliances").json() if a["id"] == "fridge")

    assert fridge["latest_watts"] == 180


# GET /appliances/{id}/readings

def plant_at(minutes_ago, watts, appliance_id="fridge"):
    with app.state.pool.connection() as conn:
        conn.execute(
            "INSERT INTO reading (appliance_id, watts, recorded_at) "
            "VALUES (%s, %s, now() - make_interval(mins => %s))",
            (appliance_id, watts, minutes_ago),
        )


def test_readings_for_an_unknown_appliance_is_404(client):
    assert client.get("/appliances/toaster/readings").status_code == 404


def test_readings_are_ordered_oldest_first_within_the_span(client):
    plant_at(20, 100)
    plant_at(5, 200)
    plant_at(10, 150)

    r = client.get("/appliances/fridge/readings?minutes=30")

    assert r.status_code == 200
    assert [row["watts"] for row in r.json()] == [100, 150, 200]


def test_readings_outside_the_span_are_excluded(client):
    plant_at(90, 999)
    plant_at(5, 200)

    r = client.get("/appliances/fridge/readings?minutes=30")

    assert [row["watts"] for row in r.json()] == [200]


def test_readings_rejects_a_non_positive_span(client):
    assert client.get("/appliances/fridge/readings?minutes=0").status_code == 422


# GET /decisions

def set_decided_at(decision_id, when):
    with app.state.pool.connection() as conn:
        conn.execute("UPDATE triage_decision SET decided_at = %s::timestamptz WHERE id = %s", (when, decision_id))


def test_decisions_include_reasoning_gate_reason_evidence_and_trace(client):
    make_decision()

    body = client.get("/decisions").json()

    assert len(body) == 1
    entry = body[0]
    assert entry["outcome"] == "escalated"
    assert entry["reasoning"] == "Some reasoning."
    assert entry["gate_reason"] == "test"
    assert entry["evidence"] == {"watts": 600}
    assert entry["tool_trace"] == [{"tool": "get_appliance_profile"}]


def test_decisions_are_newest_first(client):
    older = make_decision()
    newer = make_decision()
    set_decided_at(older, "2020-01-01T00:00:00Z")
    set_decided_at(newer, "2024-01-01T00:00:00Z")

    body = client.get("/decisions").json()

    assert [d["id"] for d in body] == [newer, older]


def test_a_pending_candidate_is_visible_as_pending(client):
    candidate_id = make_candidate()

    body = client.get("/decisions").json()

    assert len(body) == 1
    assert body[0]["outcome"] == "pending"
    assert body[0]["candidate_id"] == candidate_id
    assert body[0]["id"] is None


def test_decisions_can_be_filtered_by_outcome(client):
    make_decision(outcome="escalated")
    make_decision(outcome="resolved")
    make_candidate()

    body = client.get("/decisions?outcome=resolved").json()

    assert len(body) == 1
    assert body[0]["outcome"] == "resolved"


def test_decisions_can_be_limited(client):
    make_decision()
    make_decision()

    body = client.get("/decisions?limit=1").json()

    assert len(body) == 1


# CORS

def test_cors_origins_is_empty_by_default(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    assert cors_origins() == []


def test_cors_origins_reads_a_comma_separated_list(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://dashboard.example, https://other.example")

    assert cors_origins() == ["https://dashboard.example", "https://other.example"]


def test_an_unconfigured_origin_is_not_allowed_by_default(client):
    # CORS_ORIGINS is unset in the test environment, so the real middleware, not just
    # cors_origins() in isolation, must deny every origin rather than allow everything.
    r = client.get("/appliances", headers={"Origin": "https://anything.example"})

    assert "access-control-allow-origin" not in r.headers
