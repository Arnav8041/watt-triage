"""The triage agent: a hand-written tool-calling loop (ADR-0005). The gate makes the final call.

Env vars: AGENT_MODEL (claude-haiku-4-5), AGENT_TIMEOUT_SECONDS (30), AGENT_MAX_TURNS (6).
"""
import json
import os
import time
from typing import Literal

import anthropic
from pydantic import BaseModel, ConfigDict, ValidationError

from app import db, gate

SYSTEM = (
    "You triage one suspicious power reading in a home. Use get_appliance_profile to find out what "
    "the appliance is and its rated wattage. If it would help, use get_recent_readings to see the shape "
    "of the trace around the reading, and get_recent_decisions to see what was concluded last time. "
    "Only look up what you need. Then call submit_triage_decision exactly once. "
    "Write the reasoning in plain language for the homeowner. Say 'certain' only if the reading is "
    "clearly harmless; if you are at all unsure, say 'unsure' and escalate."
)

# For a Rated Breach the outcome is already fixed, so the prose has to fit it (ADR-0001).
BREACH_NOTE = (
    " This reading exceeded the appliance's rated wattage, so it will be escalated to the homeowner "
    "whatever you decide. Write the reasoning to explain plainly why that matters and what to check."
)


class AgentFailure(Exception):
    """A failure we can name. Always ends in an Escalation."""


class Recommendation(BaseModel):
    """What the agent hands in. Doubles as the terminal tool's schema."""

    model_config = ConfigDict(extra="forbid")
    outcome: Literal["escalate", "resolve_quietly"]
    confidence: Literal["certain", "likely", "unsure"]
    reasoning: str


TOOLS = [
    {
        "name": "get_appliance_profile",
        "description": "Look up an appliance's name, location and rated wattage (its safe maximum).",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"appliance_id": {"type": "string"}},
            "required": ["appliance_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_recent_readings",
        "description": "The appliance's power readings from N minutes before to N minutes after the "
        "flagged reading (at most 60), oldest first. Shows whether it was a sudden step or a gradual "
        "climb, and whether it held or bounced back.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"appliance_id": {"type": "string"}, "minutes": {"type": "integer"}},
            "required": ["appliance_id", "minutes"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_recent_decisions",
        "description": "What was concluded the last few times this appliance was triaged (at most 10), "
        "newest first. outcome is 'escalated' or 'resolved' (closed quietly, same as resolve_quietly). "
        "A rated_breach trigger or a gate_reason means the gate, not the earlier reasoning, decided it. "
        "Use it to see whether similar behaviour was benign before.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"appliance_id": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["appliance_id", "limit"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_triage_decision",
        "description": "Your final answer. Ends the investigation.",
        "strict": True,
        "input_schema": Recommendation.model_json_schema(),
    },
]


def model():
    return os.environ.get("AGENT_MODEL", "claude-haiku-4-5")


def timeout():
    return float(os.environ.get("AGENT_TIMEOUT_SECONDS", 30))  # per call, and checked between turns


def max_turns():
    return int(os.environ.get("AGENT_MAX_TURNS", 6))  # model replies before giving up


def run_tool(pool, name, args, detected_at):
    if name not in ("get_appliance_profile", "get_recent_readings", "get_recent_decisions"):
        return {"error": f"unknown tool {name}"}
    appliance = db.get_appliance(pool, args["appliance_id"])
    if appliance is None:  # a typo'd id must not look like "no history"
        return {"error": "no such appliance"}
    if name == "get_appliance_profile":
        return appliance
    if name == "get_recent_readings":
        return db.get_recent_readings(pool, appliance["id"], args["minutes"], detected_at)
    return db.get_recent_decisions(pool, appliance["id"], args["limit"])


def decide(client, pool, candidate, trace):
    """Loop until the model calls submit_triage_decision. Every tool call goes into `trace`."""
    # no appliance name or rated wattage in the prompt on purpose: the agent has to fetch them
    system = SYSTEM + BREACH_NOTE if candidate["trigger"] == "rated_breach" else SYSTEM
    prompt = {k: candidate[k] for k in ("appliance_id", "watts", "trigger", "detected_at")}
    messages: list[dict] = [{"role": "user", "content": json.dumps(prompt)}]
    deadline = time.monotonic() + timeout()
    for _ in range(max_turns()):
        time_left = deadline - time.monotonic()
        if time_left <= 0:
            raise AgentFailure("timed out")
        response = client.messages.create(
            model=model(), max_tokens=1024, system=system, tools=TOOLS, messages=messages,
            timeout=time_left,
        )
        calls = [block for block in response.content if block.type == "tool_use"]
        if not calls:
            raise AgentFailure("model stopped without calling submit_triage_decision")
        results = []
        for call in calls:
            if call.name == "submit_triage_decision":
                trace.append({"tool": call.name, "input": call.input})
                try:
                    return Recommendation(**call.input)
                except ValidationError:
                    raise AgentFailure("malformed submit_triage_decision call")
            step = {"tool": call.name, "input": call.input}
            trace.append(step)  # log it first, so a crash still shows what was tried
            output = step["output"] = run_tool(pool, call.name, call.input, candidate["detected_at"])
            results.append(
                {"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(output)}
            )
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": results})
    raise AgentFailure(f"turn cap of {max_turns()} reached")


def explain(client, pool, candidate, trace):
    """Rated Breach path (ADR-0001): the outcome is already fixed, so keep only the prose."""
    return decide(client, pool, candidate, trace).reasoning


def describe_failure(error):
    if isinstance(error, AgentFailure):
        return str(error)
    if isinstance(error, anthropic.APITimeoutError):
        return "timed out"
    if isinstance(error, anthropic.APIError):
        return f"API error ({type(error).__name__})"
    return f"unexpected error ({type(error).__name__})"  # our bug, not the API's


def triage(pool, client, candidate_id):
    """Investigate one Anomaly Candidate and record exactly one Triage Decision."""
    candidate = db.get_candidate(pool, candidate_id)
    trace = []
    started = time.monotonic()
    recommendation = reasoning = failure = None
    try:
        if candidate["trigger"] == "rated_breach":
            reasoning = explain(client, pool, candidate, trace)
        else:
            recommendation = decide(client, pool, candidate, trace)
            reasoning = recommendation.reasoning
    except Exception as error:  # any failure escalates (ADR-0005)
        failure = describe_failure(error)

    if failure and candidate["trigger"] != "rated_breach":
        outcome, gate_reason = "escalated", f"agent failed: {failure}"
    else:  # a breach keeps its own reason even if the agent failed
        rated_watts = db.get_appliance(pool, candidate["appliance_id"])["rated_watts"]
        cooldown_active = db.has_unacknowledged_escalation(pool, candidate["appliance_id"], gate.cooldown_hours())
        outcome, gate_reason = gate.decide(candidate, recommendation, rated_watts, cooldown_active)
        if failure:
            gate_reason += f" (agent failed: {failure})"
    confidence = recommendation.confidence if recommendation else None
    latency_ms = round((time.monotonic() - started) * 1000)
    # the Candidate plus what the tools returned, so it outlives the raw Readings (ADR-0004)
    evidence = {**candidate, "tool_results": [step for step in trace if "output" in step]}
    db.insert_decision(
        pool, candidate_id, outcome, confidence, gate_reason, reasoning, evidence, trace, model(), latency_ms
    )
