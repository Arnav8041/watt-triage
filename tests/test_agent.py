from datetime import datetime, timezone

import anthropic
import httpx2
import pytest

from app import db
from app.agent import triage
from app.main import app
from tests.fakes import ScriptedClient, submit, tool_use


def make_candidate(trigger="statistical", appliance_id="space_heater", watts=600, baseline_size=100):
    with app.state.pool.connection() as conn:
        return conn.execute(
            "INSERT INTO anomaly_candidate (appliance_id, watts, trigger, baseline_size) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (appliance_id, watts, trigger, baseline_size),
        ).fetchone()[0]


def decisions_for(candidate_id):
    with app.state.pool.connection() as conn:
        return conn.execute(
            "SELECT outcome, confidence, gate_reason, reasoning FROM triage_decision "
            "WHERE candidate_id = %s",
            (candidate_id,),
        ).fetchall()


def candidate_status(candidate_id):
    with app.state.pool.connection() as conn:
        return conn.execute(
            "SELECT status FROM anomaly_candidate WHERE id = %s", (candidate_id,)
        ).fetchone()[0]


def profile_call():
    return [tool_use("get_appliance_profile", appliance_id="space_heater")]


def test_certain_agent_and_every_check_passing_resolves_quietly(client):
    cid = make_candidate()
    fake = ScriptedClient(profile_call(), [submit("resolve_quietly", "certain", "Normal cycling.")])

    triage(app.state.pool, fake, cid)

    assert decisions_for(cid) == [("resolved", "certain", "all checks passed", "Normal cycling.")]
    assert candidate_status(cid) == "decided"


def test_agent_recommending_escalation_escalates(client):
    cid = make_candidate()
    fake = ScriptedClient(profile_call(), [submit("escalate", "certain", "That is far too high.")])

    triage(app.state.pool, fake, cid)

    assert decisions_for(cid) == [
        ("escalated", "certain", "agent recommended escalation", "That is far too high.")
    ]


@pytest.mark.parametrize("confidence", ["likely", "unsure"])
def test_confidence_below_certain_escalates(client, confidence):
    cid = make_candidate()
    fake = ScriptedClient(profile_call(), [submit("resolve_quietly", confidence)])

    triage(app.state.pool, fake, cid)

    (outcome, _, gate_reason, _), = decisions_for(cid)
    assert (outcome, gate_reason) == ("escalated", f"agent confidence is '{confidence}', not 'certain'")


def test_baseline_too_small_escalates_even_when_agent_is_certain(client):
    cid = make_candidate(baseline_size=10)
    fake = ScriptedClient(profile_call(), [submit("resolve_quietly", "certain")])

    triage(app.state.pool, fake, cid)

    (outcome, _, gate_reason, _), = decisions_for(cid)
    assert (outcome, gate_reason) == ("escalated", "baseline of 10 readings is below the minimum of 30")


@pytest.mark.parametrize("watts", [1200, 1300])  # 80% of the heater's 1500W rating, and above it
def test_reading_close_to_rated_wattage_escalates_even_when_agent_is_certain(client, watts):
    cid = make_candidate(watts=watts)
    fake = ScriptedClient(profile_call(), [submit("resolve_quietly", "certain")])

    triage(app.state.pool, fake, cid)

    (outcome, _, gate_reason, _), = decisions_for(cid)
    assert (outcome, gate_reason) == ("escalated", f"{watts}W is at or above 80% of the 1500W rated wattage")


def test_breach_escalates_despite_agent(client):
    cid = make_candidate(trigger="rated_breach", watts=3180, baseline_size=0)
    fake = ScriptedClient(profile_call(), [submit("resolve_quietly", "certain", "Heater is just warming up.")])

    triage(app.state.pool, fake, cid)

    # outcome decided by the gate, confidence discarded, the agent's prose kept
    assert decisions_for(cid) == [
        ("escalated", None, "rated breach: reading is above the appliance's rated wattage", "Heater is just warming up.")
    ]


FAILURES = {
    "malformed terminal call": (
        [[submit("escalate", "very sure")]], {}, "malformed submit_triage_decision call"
    ),
    "no terminal call": ([[]], {}, "model stopped without calling submit_triage_decision"),
    "turn cap": ([profile_call(), profile_call()], {"AGENT_MAX_TURNS": "2"}, "turn cap of 2 reached"),
    "api timeout": (
        [anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com"))], {}, "timed out"
    ),
    "wall-clock deadline": ([], {"AGENT_TIMEOUT_SECONDS": "0"}, "timed out"),
    "transport error": (
        [anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com"))],
        {},
        "API error (APIConnectionError)",
    ),
    "bug in our own code": ([RuntimeError("boom")], {}, "unexpected error (RuntimeError)"),
}


@pytest.mark.parametrize("script, env, reason", FAILURES.values(), ids=FAILURES.keys())
def test_every_failure_escalates_and_names_itself(client, monkeypatch, script, env, reason):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    cid = make_candidate()

    triage(app.state.pool, ScriptedClient(*script), cid)

    assert decisions_for(cid) == [("escalated", None, f"agent failed: {reason}", None)]


def stored(candidate_id):
    with app.state.pool.connection() as conn:
        return conn.execute(
            "SELECT evidence, tool_trace FROM triage_decision WHERE candidate_id = %s", (candidate_id,)
        ).fetchone()


def test_decision_stores_the_evidence_and_the_ordered_tool_trace(client):
    cid = make_candidate(watts=600, baseline_size=100)
    fake = ScriptedClient(profile_call(), [submit("resolve_quietly", "certain")])

    triage(app.state.pool, fake, cid)

    evidence, trace = stored(cid)
    assert (evidence["watts"], evidence["baseline_size"]) == (600, 100)
    assert [step["tool"] for step in trace] == ["get_appliance_profile", "submit_triage_decision"]
    assert trace[0]["output"]["rated_watts"] == 1500


def readings_call(minutes=10):
    return [tool_use("get_recent_readings", appliance_id="space_heater", minutes=minutes)]


def test_agent_can_look_at_the_recent_readings_oldest_first(client):
    db.seed_readings(app.state.pool, "space_heater", [100, 110, 120])
    cid = make_candidate()
    fake = ScriptedClient(readings_call(), [submit("resolve_quietly", "certain")])

    triage(app.state.pool, fake, cid)

    _, trace = stored(cid)
    assert [r["watts"] for r in trace[0]["output"]] == [100, 110, 120]


def test_a_span_with_no_readings_gives_an_empty_result_not_an_error(client):
    cid = make_candidate()
    fake = ScriptedClient(readings_call(), [submit("resolve_quietly", "certain")])

    triage(app.state.pool, fake, cid)

    _, trace = stored(cid)
    assert trace[0]["output"] == []
    assert decisions_for(cid)[0][0] == "resolved"  # and it carried on to decide


def test_agent_can_look_up_what_was_concluded_last_time(client):
    earlier = make_candidate()
    triage(app.state.pool, ScriptedClient(profile_call(), [submit("resolve_quietly", "certain", "Normal cycling.")]), earlier)
    now = make_candidate()
    ask = [tool_use("get_recent_decisions", appliance_id="space_heater", limit=5)]

    triage(app.state.pool, ScriptedClient(ask, [submit("resolve_quietly", "certain")]), now)

    _, trace = stored(now)
    (precedent,) = trace[0]["output"]
    assert (precedent["outcome"], precedent["confidence"], precedent["reasoning"]) == (
        "resolved", "certain", "Normal cycling."
    )


def test_evidence_snapshots_what_the_tools_returned_and_the_trace_keeps_their_order(client):
    db.seed_readings(app.state.pool, "space_heater", [100, 110, 120])
    cid = make_candidate()
    history = [tool_use("get_recent_decisions", appliance_id="space_heater", limit=5)]
    fake = ScriptedClient(readings_call(), history, [submit("resolve_quietly", "certain")])

    triage(app.state.pool, fake, cid)

    evidence, trace = stored(cid)
    assert [step["tool"] for step in trace] == [
        "get_recent_readings", "get_recent_decisions", "submit_triage_decision"
    ]
    assert [seen["tool"] for seen in evidence["tool_results"]] == ["get_recent_readings", "get_recent_decisions"]
    assert [r["watts"] for r in evidence["tool_results"][0]["output"]] == [100, 110, 120]
    assert evidence["watts"] == 600  # the Candidate itself is still in there


def test_trace_is_kept_when_the_run_fails_part_way(client, monkeypatch):
    monkeypatch.setenv("AGENT_MAX_TURNS", "1")  # one look-up, then the cap hits
    cid = make_candidate()

    triage(app.state.pool, ScriptedClient(profile_call()), cid)

    _, trace = stored(cid)
    assert [step["tool"] for step in trace] == ["get_appliance_profile"]


def test_agent_is_told_only_about_the_candidate(client):
    cid = make_candidate()
    fake = ScriptedClient(profile_call(), [submit("resolve_quietly", "certain")])

    triage(app.state.pool, fake, cid)

    first_prompt = fake.calls[0]["messages"][0]["content"]
    assert "space_heater" in first_prompt
    assert "Space heater" not in first_prompt and "1500" not in first_prompt  # it must fetch these


def test_breach_stays_a_breach_escalation_when_the_agent_fails(client):
    cid = make_candidate(trigger="rated_breach", watts=3180, baseline_size=0)

    triage(app.state.pool, ScriptedClient(RuntimeError("boom")), cid)

    assert decisions_for(cid) == [
        (
            "escalated",
            None,
            "rated breach: reading is above the appliance's rated wattage (agent failed: unexpected error (RuntimeError))",
            None,
        )
    ]


def test_agent_is_told_a_breach_will_be_escalated_so_its_prose_fits(client):
    breach = make_candidate(trigger="rated_breach", watts=3180, baseline_size=0)
    ordinary = make_candidate()
    fakes = [ScriptedClient(profile_call(), [submit("escalate", "certain")]) for _ in range(2)]

    triage(app.state.pool, fakes[0], breach)
    triage(app.state.pool, fakes[1], ordinary)

    assert "will be escalated" in fakes[0].calls[0]["system"]
    assert "will be escalated" not in fakes[1].calls[0]["system"]


def test_a_huge_span_is_capped_at_an_hour(client):
    db.seed_readings(app.state.pool, "space_heater", [1, 2, 3], interval_seconds=40 * 60)  # 120, 80, 40 min ago

    readings = db.get_recent_readings(app.state.pool, "space_heater", 1_000_000, datetime.now(timezone.utc))

    assert [r["watts"] for r in readings] == [3]


def test_recent_decisions_come_newest_first_and_are_capped_at_ten(client):
    for i in range(1, 12):
        script = ScriptedClient(profile_call(), [submit("escalate", "certain", f"decision {i}")])
        triage(app.state.pool, script, make_candidate())

    decisions = db.get_recent_decisions(app.state.pool, "space_heater", 1_000_000)

    assert [d["reasoning"] for d in decisions] == [f"decision {i}" for i in range(11, 1, -1)]


def test_the_agent_is_offered_exactly_the_read_only_tools_and_the_terminal_one(client):
    fake = ScriptedClient(profile_call(), [submit("resolve_quietly", "certain")])

    triage(app.state.pool, fake, make_candidate())

    offered = {tool["name"] for tool in fake.calls[0]["tools"]}
    assert offered == {
        "get_appliance_profile", "get_recent_readings", "get_recent_decisions", "submit_triage_decision"
    }


def test_no_decisions_or_a_nonsense_limit_gives_an_empty_result_not_an_error(client):
    assert db.get_recent_decisions(app.state.pool, "space_heater", 5) == []
    assert db.get_recent_decisions(app.state.pool, "space_heater", -1) == []


@pytest.mark.parametrize("tool, arg", [("get_recent_readings", {"minutes": 10}), ("get_recent_decisions", {"limit": 5})])
def test_asking_about_an_unknown_appliance_gets_an_error_the_agent_can_read(client, tool, arg):
    cid = make_candidate()
    fake = ScriptedClient([tool_use(tool, appliance_id="toaster", **arg)], [submit("escalate", "unsure")])

    triage(app.state.pool, fake, cid)

    _, trace = stored(cid)
    assert trace[0]["output"] == {"error": "no such appliance"}


def test_a_tool_call_that_crashes_is_still_in_the_trace(client):
    cid = make_candidate()
    bad_call = [tool_use("get_recent_readings", appliance_id="space_heater", minutes="ten")]

    triage(app.state.pool, ScriptedClient(bad_call), cid)

    evidence, trace = stored(cid)
    assert trace == [{"tool": "get_recent_readings", "input": {"appliance_id": "space_heater", "minutes": "ten"}}]
    assert evidence["tool_results"] == []  # it never returned anything
    assert decisions_for(cid) == [("escalated", None, "agent failed: unexpected error (TypeError)", None)]


def test_readings_are_centred_on_the_candidate_even_when_triage_runs_late(client):
    cid = make_candidate()  # then backdate it 3 hours
    with app.state.pool.connection() as conn:
        conn.execute("UPDATE anomaly_candidate SET detected_at = now() - interval '180 minutes' WHERE id = %s", (cid,))
        for watts, minutes_ago in [(1, 215), (2, 185), (3, 175), (4, 100)]:  # event is 180 min ago
            conn.execute(
                "INSERT INTO reading (appliance_id, watts, recorded_at) "
                "VALUES ('space_heater', %s, now() - make_interval(mins => %s))",
                (watts, minutes_ago),
            )
    fake = ScriptedClient(readings_call(minutes=10), [submit("escalate", "unsure")])

    triage(app.state.pool, fake, cid)

    _, trace = stored(cid)
    assert [r["watts"] for r in trace[0]["output"]] == [2, 3]  # 5 min before and 5 min after the event


def test_precedent_shows_when_the_gate_rather_than_the_agent_forced_the_outcome(client):
    breach = make_candidate(trigger="rated_breach", watts=3180, baseline_size=0)
    triage(app.state.pool, ScriptedClient(profile_call(), [submit("resolve_quietly", "certain", "Just warming up.")]), breach)
    now = make_candidate()
    ask = [tool_use("get_recent_decisions", appliance_id="space_heater", limit=5)]

    triage(app.state.pool, ScriptedClient(ask, [submit("escalate", "unsure")]), now)

    _, trace = stored(now)
    (precedent,) = trace[0]["output"]
    assert precedent["trigger"] == "rated_breach"
    assert precedent["gate_reason"] == "rated breach: reading is above the appliance's rated wattage"
