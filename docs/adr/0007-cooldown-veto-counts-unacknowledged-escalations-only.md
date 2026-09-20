# The escalation cooldown veto counts only unacknowledged Escalations

The gate vetoes Quiet Resolution when the Appliance has a recent Escalation, so that a
developing fault is not progressively normalised. Counting *every* recent Escalation turned
out to be wrong: because a routine duty cycle does raise an Anomaly Candidate (see
ADR-0008), a single Escalation would force every subsequent compressor start on that
Appliance to escalate for a full day. That is an alert storm, which is the exact failure the
whole project exists to avoid.

The veto therefore counts only Escalations that have not been acknowledged. Acknowledgement
lifts it immediately.

## Consequences

Acknowledgement is load-bearing, not cosmetic — it is the homeowner's signal that the
Appliance is no longer in a raised state. It should not be removed as "just CRUD", and the
gate must never be changed to count acknowledged Escalations.
