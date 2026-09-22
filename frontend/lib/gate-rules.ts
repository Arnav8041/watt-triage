import type { Decision } from "./types";

/**
 * Mirrors the ordered checks in app/gate.py, first match wins. Kept as a plain, fixed
 * list on purpose — it's meant to look like what it is: a small set of rules, not a model.
 */
export type GateRule = {
  label: string;
  matches: (decision: Decision) => boolean;
};

export const GATE_RULES: GateRule[] = [
  {
    label: "Reading is above the appliance's rated wattage (Rated Breach)",
    matches: (d) => d.trigger === "rated_breach",
  },
  {
    label: "Agent recommended escalation",
    matches: (d) => d.gate_reason === "agent recommended escalation",
  },
  {
    label: "Agent confidence wasn't 'certain'",
    matches: (d) => (d.gate_reason ?? "").startsWith("agent confidence is"),
  },
  {
    label: "Not enough baseline history yet",
    matches: (d) => (d.gate_reason ?? "").startsWith("baseline of"),
  },
  {
    label: "Reading is too close to the rated wattage (headroom)",
    matches: (d) => (d.gate_reason ?? "").includes("is at or above"),
  },
  {
    label: "An unacknowledged escalation on this appliance is still active",
    matches: (d) => (d.gate_reason ?? "").includes("unacknowledged escalation"),
  },
  {
    label: "All checks passed — resolved quietly",
    matches: (d) => d.gate_reason === "all checks passed",
  },
];
