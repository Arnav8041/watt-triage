"""The gate: plain code that turns the agent's recommendation into the real outcome (ADR-0003).

The agent can permit silence but never force it. Rules run in order, first match wins.
"""
import os

from app import detector


def headroom_fraction():
    return float(os.environ.get("GATE_HEADROOM_FRACTION", 0.8))  # how close to the limit is too close


def cooldown_hours():
    return float(os.environ.get("GATE_COOLDOWN_HOURS", 24))  # hours an unacknowledged Escalation blocks quiet resolution


def decide(candidate, recommendation, rated_watts, cooldown_active):
    """Returns (outcome, gate_reason). cooldown_active: a recent unacknowledged Escalation on this Appliance."""
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
    if cooldown_active:  # unacknowledged only (ADR-0007)
        return "escalated", f"unacknowledged escalation on this appliance within the last {cooldown_hours():g}h"
    return "resolved", "all checks passed"
