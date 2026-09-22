from app import agent, db
from app.agent import triage
from app.main import app
from tests.fakes import ScriptedClient, submit
from tests.test_agent import make_candidate, decisions_for, profile_call


def plant_agent_runs(n):
    """n prior Triage Decisions that made a real model call, as if from before a restart."""
    for _ in range(n):
        triage(
            app.state.pool,
            ScriptedClient(profile_call(), [submit("resolve_quietly", "certain")]),
            make_candidate(),
        )


def test_under_the_budget_behaves_exactly_as_today(client, monkeypatch):
    monkeypatch.setenv("AGENT_MAX_RUNS_PER_HOUR", "5")
    cid = make_candidate()
    fake = ScriptedClient(profile_call(), [submit("resolve_quietly", "certain", "Normal cycling.")])

    triage(app.state.pool, fake, cid)

    assert decisions_for(cid) == [("resolved", "certain", "all checks passed", "Normal cycling.")]
    assert len(fake.calls) == 2  # the profile lookup, then the terminal call


def test_under_the_budget_a_rated_breach_still_gets_its_explanation_call(client, monkeypatch):
    monkeypatch.setenv("AGENT_MAX_RUNS_PER_HOUR", "5")
    cid = make_candidate(trigger="rated_breach", watts=3180, baseline_size=0)
    fake = ScriptedClient(profile_call(), [submit("resolve_quietly", "certain", "Just warming up.")])

    triage(app.state.pool, fake, cid)

    assert decisions_for(cid) == [
        ("escalated", None, "rated breach: reading is above the appliance's rated wattage", "Just warming up.")
    ]
    assert len(fake.calls) == 2  # the model was consulted for the prose, same as before this ticket


def test_over_the_budget_escalates_without_calling_the_model(client, monkeypatch):
    monkeypatch.setenv("AGENT_MAX_RUNS_PER_HOUR", "2")
    plant_agent_runs(2)  # uses up the budget
    cid = make_candidate()
    fake = ScriptedClient()  # any call at all would raise (out of script)

    triage(app.state.pool, fake, cid)

    assert fake.calls == []
    (outcome, confidence, gate_reason, reasoning), = decisions_for(cid)
    assert outcome == "escalated"
    assert confidence is None
    assert reasoning is None
    assert gate_reason == "agent failed: budget of 2 runs/hour reached"


def test_rated_breach_over_the_budget_still_escalates_as_a_breach_with_no_model_call(client, monkeypatch):
    monkeypatch.setenv("AGENT_MAX_RUNS_PER_HOUR", "1")
    plant_agent_runs(1)
    cid = make_candidate(trigger="rated_breach", watts=3180, baseline_size=0)
    fake = ScriptedClient()

    triage(app.state.pool, fake, cid)

    assert fake.calls == []
    (outcome, _, gate_reason, reasoning), = decisions_for(cid)
    assert outcome == "escalated"
    assert gate_reason == (
        "rated breach: reading is above the appliance's rated wattage (agent failed: budget of 1 runs/hour reached)"
    )
    assert reasoning is None


def test_a_budget_skipped_decision_does_not_count_toward_its_own_cap(client, monkeypatch):
    monkeypatch.setenv("AGENT_MAX_RUNS_PER_HOUR", "1")
    plant_agent_runs(1)  # uses the one slot
    triage(app.state.pool, ScriptedClient(), make_candidate())  # this one is budget-skipped

    assert db.agent_runs_this_hour(app.state.pool) == 1  # the skip didn't add another real run


def test_the_count_is_read_from_the_database_not_in_process_state(client, monkeypatch):
    monkeypatch.setenv("AGENT_MAX_RUNS_PER_HOUR", "3")
    plant_agent_runs(3)  # as if these ran before a restart, with nothing kept in memory

    assert db.agent_runs_this_hour(app.state.pool) == 3


def test_decisions_older_than_an_hour_do_not_count_toward_the_budget(client):
    plant_agent_runs(1)
    with app.state.pool.connection() as conn:
        conn.execute("UPDATE triage_decision SET decided_at = now() - interval '2 hours'")

    assert db.agent_runs_this_hour(app.state.pool) == 0


def test_default_budget_has_a_sensible_positive_default(monkeypatch):
    monkeypatch.delenv("AGENT_MAX_RUNS_PER_HOUR", raising=False)
    assert agent.hourly_budget() > 0
