# Rated Breach escalates without agent judgement

A Reading above its Appliance's Rated Wattage is a physical safety condition, not a
statistical one, so the escalation is decided in deterministic code *before* the agent is
invoked. The agent is still called on this path, but only to produce the homeowner-facing
explanation — its proposed outcome and confidence are discarded.

The one exception is the hourly agent budget (ticket #16): if the cap on paid model calls
has already been reached this hour, the explanation call is skipped too, same as any other
Candidate. The Reading is still recorded and still escalated as a Rated Breach — only the
prose is missing, and the gate reason says why.

## Considered Options

- **Treat a Rated Breach as an ordinary Anomaly Candidate.** One code path, no special
  case. Rejected: a hallucinated high confidence could suppress a genuine fire risk, and
  that is not defensible.
- **Short-circuit with a templated string, no model call.** Cheapest and fastest.
  Rejected: the system's most important output would contain no reasoning worth reading.

## Consequences

There are two agent entry points, not one: `decide()` (returns an outcome) and
`explain()` (returns prose only). A reader encountering the special case in the pipeline
should not collapse them back together.
