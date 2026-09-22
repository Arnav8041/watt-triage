"use client";

import { motion } from "motion/react";
import { Sparkline } from "./Sparkline";
import { severityOf } from "@/lib/severity";
import type { Appliance, Reading } from "@/lib/types";

// three genuinely different hues, not shades of one color — severity has to read at a
// glance, and "hot" pulsing the same amber as "breach" would only differ once you stopped
// to compare them side by side
const COLOR = { normal: "var(--safe)", hot: "var(--warn)", breach: "var(--danger)" };
const LABEL = { normal: "Normal", hot: "Running hot", breach: "Rated breach" };

export function ApplianceCard({ appliance, readings }: { appliance: Appliance; readings: Reading[] }) {
  const severity = severityOf(appliance);
  const color = COLOR[severity];

  return (
    <motion.div
      layout
      className="flex flex-col gap-2 rounded-md border p-3"
      style={{ borderColor: severity === "normal" ? "var(--line)" : color, background: "var(--surface)" }}
      // a breach pulses like a hazard light — the one non-interactive motion on this strip,
      // reserved for the state that actually needs a second glance
      animate={
        severity === "breach"
          ? { boxShadow: ["0 0 0 0 rgba(232,163,61,0)", "0 0 0 4px rgba(232,163,61,0.25)", "0 0 0 0 rgba(232,163,61,0)"] }
          : { boxShadow: "0 0 0 0 rgba(0,0,0,0)" }
      }
      transition={severity === "breach" ? { duration: 1.6, repeat: Infinity, ease: "easeInOut" } : { duration: 0.3 }}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm text-ink">{appliance.name}</span>
        <span
          className="h-2 w-2 shrink-0 rounded-full"
          style={{ background: severity === "normal" ? "var(--safe)" : color }}
          title={LABEL[severity]}
        />
      </div>
      <div className="tnum text-lg text-ink">
        {appliance.latest_watts != null ? `${Math.round(appliance.latest_watts)}W` : "—"}
        <span className="ml-1 text-xs text-ink-dim">/ {appliance.rated_watts}W</span>
      </div>
      <Sparkline readings={readings} color={color} />
      <span className="text-xs" style={{ color: severity === "normal" ? "var(--ink-dim)" : color }}>
        {LABEL[severity]}
      </span>
    </motion.div>
  );
}
