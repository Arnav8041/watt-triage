# Triage Decisions snapshot their evidence instead of referencing it

Raw Readings are rolled up to hourly aggregates and deleted, so an audit record that
pointed at Reading rows would, by design, end up citing evidence that no longer exists.
Each Triage Decision therefore stores a JSONB snapshot of what the agent actually saw —
the surrounding trace, the baseline statistics, and the sequence of tool calls it made —
at the moment the decision was taken.

This keeps the retention job a single unqualified `DELETE` with no carve-outs, and makes
the audit record immutable and self-contained, in the same way an invoice records the
price paid rather than joining to today's price list.

## Consequences

Evidence bytes are duplicated between `readings` and `triage_decisions.evidence`. That is
deliberate. Do not normalise it away, and do not add a foreign key from a decision to a
reading that the retention job is free to delete.
