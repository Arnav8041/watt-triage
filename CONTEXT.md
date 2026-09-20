# WattTriage

WattTriage watches electrical power draw from a small set of home appliances and decides,
per suspicious reading, whether it can be closed quietly or must be put in front of the
homeowner. Every decision is recorded with its reasoning.

## Language

**Appliance**:
A single monitored device in the home (fridge, water heater, space heater, washer, AC unit).
Each has a manufacturer-stated power limit it should never exceed.
_Avoid_: Device, sensor, meter, load

**Reading**:
One power-draw measurement for one Appliance at one instant, in watts.
_Avoid_: Sample, datapoint, observation, event

**Rated Wattage**:
The manufacturer-stated maximum power an Appliance is designed to draw. A physical,
safety-relevant limit — not a statistical one.
_Avoid_: Max watts, threshold, limit

**Detector**:
The deterministic rules that run on every Reading and decide only whether it deserves a
second look. It never decides what to do about it.
_Avoid_: Analyser, classifier, monitor

**Anomaly Candidate**:
A Reading the Detector flagged as suspicious, awaiting a decision. It is a suspicion, not
a fault — most turn out to be benign.
_Avoid_: Anomaly, alert, incident, issue

**Triage Decision**:
The recorded outcome for one Anomaly Candidate: what was decided, by what reasoning, and
with how much confidence. Produced for both outcomes, never only for escalations.
_Avoid_: Verdict, result, judgement, classification

**Rated Breach**:
A Reading above its Appliance's Rated Wattage. A physical condition, not a statistical one.
_Avoid_: Overload, spike, over-limit

**Escalation**:
A Triage Decision that puts the situation in front of the homeowner. The default outcome
whenever anything is uncertain.
_Avoid_: Alert, alarm, notification, warning

**Quiet Resolution**:
A Triage Decision that closes an Anomaly Candidate without involving the homeowner. Still
fully recorded — quiet means unnotified, never unlogged.
_Avoid_: Auto-resolve, dismiss, ignore, suppress

**Confidence**:
The agent's self-reported certainty in its own reasoning, expressed as one of `certain`,
`likely` or `unsure`. An ordinal judgement, never a probability.
_Avoid_: Score, probability, certainty percentage

**Evidence**:
The snapshot of what the agent actually saw when it decided — the surrounding trace, the
baseline statistics, and the tool calls it chose to make. Stored on the Triage Decision and
never re-derived.
_Avoid_: Context, data, inputs

**Rollup**:
The hourly per-Appliance aggregate that raw Readings are summarised into before being
deleted.
_Avoid_: Aggregate, summary, bucket, archive
