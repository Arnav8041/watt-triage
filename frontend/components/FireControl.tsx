"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { ApiError, fireScenario, resetDemo } from "@/lib/api";
import { SCENARIOS, type Scenario } from "@/lib/types";

const SCENARIO_LABEL: Record<Scenario, string> = {
  "heater-breach": "Space heater breach",
  "washer-spin": "Washer spin-up",
  "ac-surge": "AC surge",
};

export function FireControl({ onFired }: { onFired: () => void }) {
  const [busy, setBusy] = useState<Scenario | "reset" | null>(null);
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

  async function reset() {
    if (!window.confirm("Reset the demo? This clears the decision log and replants a clean baseline.")) return;
    setBusy("reset");
    setStatus(null);
    try {
      await resetDemo();
      setStatus("Demo reset — back to a clean baseline.");
      onFired();
    } catch {
      setStatus("Couldn't reset the demo.");
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
          whileHover={{ borderColor: "var(--pending)" }}
          whileTap={{ scale: 0.96 }}
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
          className="cursor-pointer rounded-md border border-line bg-surface-raised px-4 py-2 text-sm font-medium text-ink disabled:cursor-default disabled:opacity-50"
        >
          {busy === scenario ? "Firing…" : SCENARIO_LABEL[scenario]}
        </motion.button>
      ))}

      <button
        type="button"
        onClick={reset}
        disabled={busy !== null}
        className="cursor-pointer rounded-md border border-transparent px-3 py-2 text-sm text-ink-dim underline decoration-line underline-offset-4 hover:text-ink disabled:cursor-default disabled:opacity-50"
      >
        {busy === "reset" ? "Resetting…" : "Reset demo"}
      </button>

      {status && <span className="text-sm text-ink-dim">{status}</span>}
    </div>
  );
}
