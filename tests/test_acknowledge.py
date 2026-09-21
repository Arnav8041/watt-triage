from types import SimpleNamespace

from app import db, gate
from app.agent import triage
from app.main import app
from tests.fakes import ScriptedClient, submit
from tests.test_agent import make_candidate


def make_decision(outcome="escalated", appliance_id="space_heater"):
    """Insert a decision (and its Candidate). Returns its id."""
    cid = make_candidate(appliance_id=appliance_id)
    db.insert_decision(
        app.state.pool, cid, outcome, "likely", "test", "Some reasoning.",
        {"watts": 600}, [{"tool": "get_appliance_profile"}], "test-model", 5,
    )
    with app.state.pool.connection() as conn:
        return conn.execute("SELECT id FROM triage_decision WHERE candidate_id = %s", (cid,)).fetchone()[0]


def row(decision_id):
    with app.state.pool.connection() as conn:
        return conn.execute(
            "SELECT outcome, confidence, gate_reason, reasoning, evidence, tool_trace, decided_at, acknowledged_at "
            "FROM triage_decision WHERE id = %s",
            (decision_id,),
        ).fetchone()


def test_acknowledging_an_escalation_records_the_time(client):
    did = make_decision()
    assert row(did)[-1] is None

    response = client.post(f"/decisions/{did}/acknowledge")

    assert response.status_code == 200
    assert row(did)[-1] is not None


def test_acknowledging_twice_is_fine_and_keeps_the_first_time(client):
    did = make_decision()

    first = client.post(f"/decisions/{did}/acknowledge")
    second = client.post(f"/decisions/{did}/acknowledge")

    assert second.status_code == 200
    assert second.json() == first.json()


def test_acknowledging_a_quiet_resolution_is_rejected(client):
    did = make_decision(outcome="resolved")

    response = client.post(f"/decisions/{did}/acknowledge")

    assert response.status_code == 409
    assert "Escalation" in response.json()["detail"]
    assert row(did)[-1] is None


def test_acknowledging_an_unknown_decision_is_404(client):
    assert client.post("/decisions/999999/acknowledge").status_code == 404


def test_acknowledging_edits_nothing_but_the_acknowledged_time(client):
    did = make_decision()
    before = row(did)[:-1]  # all but acknowledged_at

    client.post(f"/decisions/{did}/acknowledge")

    assert row(did)[:-1] == before


# cooldown veto

def a_would_be_quiet_triage(appliance_id="space_heater"):
    """Triage an event every other check would resolve. Returns (outcome, gate_reason)."""
    cid = make_candidate(appliance_id=appliance_id)
    fake = ScriptedClient([submit("resolve_quietly", "certain")])
    triage(app.state.pool, fake, cid)
    with app.state.pool.connection() as conn:
        return conn.execute(
            "SELECT outcome, gate_reason FROM triage_decision WHERE candidate_id = %s", (cid,)
        ).fetchone()


def test_gate_escalates_when_the_cooldown_is_active():
    candidate = {"trigger": "statistical", "baseline_size": 100, "watts": 600}
    recommendation = SimpleNamespace(outcome="resolve_quietly", confidence="certain")

    assert gate.decide(candidate, recommendation, 1500, cooldown_active=False)[0] == "resolved"
    outcome, reason = gate.decide(candidate, recommendation, 1500, cooldown_active=True)
    assert outcome == "escalated"
    assert "unacknowledged" in reason


def test_unacknowledged_escalation_vetoes_the_next_quiet_resolution(client):
    make_decision()

    outcome, reason = a_would_be_quiet_triage()

    assert outcome == "escalated"
    assert "unacknowledged" in reason


def test_acknowledging_lifts_the_veto(client):
    client.post(f"/decisions/{make_decision()}/acknowledge")

    assert a_would_be_quiet_triage()[0] == "resolved"


def test_the_veto_is_scoped_to_one_appliance(client):
    make_decision(appliance_id="space_heater")

    assert a_would_be_quiet_triage(appliance_id="washer")[0] == "resolved"


def test_an_escalation_older_than_the_window_no_longer_vetoes(client):
    did = make_decision()
    with app.state.pool.connection() as conn:
        conn.execute("UPDATE triage_decision SET decided_at = now() - interval '25 hours' WHERE id = %s", (did,))

    assert a_would_be_quiet_triage()[0] == "resolved"


def test_a_quiet_resolution_does_not_veto(client):
    make_decision(outcome="resolved")

    assert a_would_be_quiet_triage()[0] == "resolved"


def test_the_window_comes_from_the_environment(client, monkeypatch):
    did = make_decision()
    with app.state.pool.connection() as conn:
        conn.execute("UPDATE triage_decision SET decided_at = now() - interval '25 hours' WHERE id = %s", (did,))
    monkeypatch.setenv("GATE_COOLDOWN_HOURS", "48")

    assert a_would_be_quiet_triage()[0] == "escalated"
