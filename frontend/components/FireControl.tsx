"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { ApiError, fireScenario } from "@/lib/api";
import { SCENARIOS, type Scenario } from "@/lib/types";

const SCENARIO_LABEL: Record<Scenario, string> = {
  "heater-breach": "Space heater breach",
  "washer-spin": "Washer spin-up",
  "ac-surge": "AC surge",
};

export function FireControl({ onFired }: { onFired: () => void }) {
  const [busy, setBusy] = useState<Scenario | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  async function fire(scenario: Scenario) {
    setBusy(scenario);
    setStatus(null);
    try {
      await fireScenario(scenario);
      setStatus(`Fired ${SCENARIO_LABEL[scenario]} — watch it land below.`);
      onFired();
    } catch (error) {
      setStatus(
        error instanceof ApiError && error.status === 409
          ? "Already investigating — try again in a moment."
          : "Couldn't fire that scenario.",
      );
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {SCENARIOS.map((scenario) => (
        <motion.button
          key={scenario}
          type="button"
          onClick={() => fire(scenario)}
          disabled={busy !== null}
          whileTap={{ scale: 0.96 }}
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
          className="rounded-md border border-line bg-surface-raised px-3 py-1.5 text-xs text-ink disabled:opacity-50"
        >
          {busy === scenario ? "Firing…" : SCENARIO_LABEL[scenario]}
        </motion.button>
      ))}
      {status && <span className="text-xs text-ink-dim">{status}</span>}
    </div>
  );
}
