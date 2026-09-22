export type Appliance = {
  id: string;
  name: string;
  location: string;
  rated_watts: number;
  latest_watts: number | null;
  latest_recorded_at: string | null;
};

export type Reading = {
  watts: number;
  recorded_at: string;
};

export type ToolCall = {
  tool: string;
  input?: unknown;
  output?: unknown;
};

export type Outcome = "escalated" | "resolved" | "pending";
export type Confidence = "certain" | "likely" | "unsure";
export type Trigger = "rated_breach" | "statistical";

export type Decision = {
  id: number | null;
  candidate_id: number;
  appliance_id: string;
  watts: number;
  trigger: Trigger;
  outcome: Outcome;
  confidence: Confidence | null;
  gate_reason: string | null;
  reasoning: string | null;
  evidence: Record<string, unknown> | null;
  tool_trace: ToolCall[] | null;
  acknowledged_at: string | null;
  detected_at: string;
  decided_at: string | null;
};

export const SCENARIOS = ["heater-breach", "washer-spin", "ac-surge"] as const;
export type Scenario = (typeof SCENARIOS)[number];
