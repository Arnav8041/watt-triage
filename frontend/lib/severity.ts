import type { Appliance } from "./types";

// Mirrors gate.py's default GATE_HEADROOM_FRACTION. This copy is a display cue only —
// it never decides an outcome, the gate does — so a drift from the server's configured
// value costs nothing but a slightly early or late color change on the strip.
const HOT_FRACTION = 0.8;

export type Severity = "normal" | "hot" | "breach";

export function severityOf(appliance: Appliance): Severity {
  if (appliance.latest_watts == null) return "normal";
  if (appliance.latest_watts > appliance.rated_watts) return "breach";
  if (appliance.latest_watts >= HOT_FRACTION * appliance.rated_watts) return "hot";
  return "normal";
}
