# Confidence is an ordinal bucket, not a float

The agent reports `certain | likely | unsure`, never a decimal. A self-reported LLM
confidence is not a calibrated probability — there are no labelled outcomes to calibrate
against — so emitting `0.87` would claim a precision the system does not have.

A Triage Decision may be resolved quietly only when the agent says `certain` *and* every
deterministic veto passes: no Rated Breach, baseline sample size >= 30, peak below 80% of
Rated Wattage, and no Escalation for that Appliance in the last 24 hours. Anything else
escalates. The gate is fail-safe by construction: the fuzzy signal can only ever *permit*
silence, never compel it.

## Consequences

The confidence threshold is coarse and not tunable to two decimal places. That is
intended. Do not "improve" this into a float.
