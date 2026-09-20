# The agent loop is hand-written, and the agent has no write access

The agent is the part of this project that is meant to be explainable under questioning,
so the loop is roughly fifty lines written against `client.messages.create` rather than
delegated to the SDK's beta tool runner, an agents framework, or LangGraph. Turn cap,
wall-clock timeout, tool dispatch and failure behaviour are all ours to state.

The agent is given four read-only tools (`get_appliance_profile`, `get_recent_readings`,
`get_hourly_history`, `get_recent_decisions`) and one terminal tool,
`submit_triage_decision`, which ends the loop. `submit_triage_decision` *returns a
recommendation*; the surrounding code applies the gate and performs the side effect. The
model therefore has no path to mutating state, structurally rather than by instruction.

Any failure — timeout, API error, malformed output, or turn cap reached — produces an
Escalation, consistent with the fail-safe gate in ADR-0003.

## Considered Options

- **SDK tool runner (`client.beta.messages.tool_runner`).** Less code, official, typed
  schemas from signatures. Rejected because the loop is the artefact.
- **Claude Agent SDK.** Built for filesystem and shell agents; this agent needs four
  SQL-backed reads.
- **LangGraph / PydanticAI.** Real tools, but they move the interesting part of the
  project inside a dependency.
