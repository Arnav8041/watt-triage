"""The gate: plain code that turns the agent's recommendation into the real outcome (ADR-0003).

The agent can permit silence but never force it. Rules run in order, first match wins.
"""
import os

from app import detector


def headroom_fraction():
    return float(os.environ.get("GATE_HEADROOM_FRACTION", 0.8))  # how close to the limit is too close


def decide(candidate, recommendation, rated_watts):
    """Returns (outcome, gate_reason)."""
    if candidate["trigger"] == "rated_breach":  # decided before the agent is consulted (ADR-0001)
        return "escalated", "rated breach: reading is above the appliance's rated wattage"
    if recommendation.outcome == "escalate":
        return "escalated", "agent recommended escalation"
    if recommendation.confidence != "certain":
        return "escalated", f"agent confidence is '{recommendation.confidence}', not 'certain'"
    if candidate["baseline_size"] < detector.min_baseline():
        return "escalated", (
            f"baseline of {candidate['baseline_size']} readings is below the minimum of {detector.min_baseline()}"
        )
    if candidate["watts"] >= headroom_fraction() * rated_watts:
        return "escalated", (
            f"{candidate['watts']:g}W is at or above {headroom_fraction():.0%} of the {rated_watts}W rated wattage"
        )
    return "resolved", "all checks passed"
