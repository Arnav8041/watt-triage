# The Detector's limits are structural, and the agent absorbs duty cycles

Two properties of the rolling-baseline detector were measured during design rather than
assumed, and both shape the rest of the system.

**A purely linear drift is undetectable at any rate.** A faster ramp inflates the gap from
the baseline mean and the baseline's own standard deviation by the same factor, so the
z-score is invariant at roughly 1.9 and never reaches the threshold. This is not a
threshold that can be tuned; detecting drift requires a second detector working against the
hourly Rollups, which is out of scope for v1. A `fridge-drift` demo scenario was removed for
this reason.

**Persistence suppresses single-sample noise, not sustained state changes.** A fridge
compressor starting is a step to a new level that holds for minutes, so it scores an
enormous z against the idle baseline and does raise an Anomaly Candidate. This is left
as-is: closing it quietly, with a recorded reason, is precisely the agent's job, and
pre-filtering it in the Detector would move judgement back into fixed rules. Measured cost
is roughly two to four Candidates per hour across the five Appliances — comfortably under
one percent of Readings.

## Consequences

The fridge produces Quiet Resolutions continuously without anything being injected, which
is useful demonstration material. It also means the cooldown veto had to be narrowed — see
ADR-0007.
