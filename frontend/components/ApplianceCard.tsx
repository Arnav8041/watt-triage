"use client";

import { motion } from "motion/react";
import { Sparkline } from "./Sparkline";
import { severityOf } from "@/lib/severity";
import type { Appliance, Reading } from "@/lib/types";

// three genuinely different hues, not shades of one color — severity has to read at a
// glance, and "hot" glowing the same color as "breach" would only differ once you stopped
// to compare them side by side
const COLOR = { normal: "var(--safe)", hot: "var(--hot)", breach: "var(--breach)" };
const LABEL = { normal: "Normal", hot: "Running hot", breach: "Rated breach" };

// the card's own entrance — inherited from ApplianceStrip's "hidden"/"visible" toggle,
// staggered per column, so the whole rack reads as one instrument switching on
const entrance = { hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" as const } } };

export function ApplianceCard({ appliance, readings }: { appliance: Appliance; readings: Reading[] }) {
  const severity = severityOf(appliance);
  const color = COLOR[severity];

  return (
    <motion.div variants={entrance} className="flex min-w-0 flex-1 flex-col gap-2 px-4 py-4">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm text-ink-dim">{appliance.name}</span>
        <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color }} title={LABEL[severity]} />
      </div>

      <motion.div
        className={`tnum whitespace-nowrap text-3xl font-medium text-ink ${severity === "hot" ? "glow-hot" : severity === "breach" ? "glow-breach" : ""}`}
        style={severity !== "normal" ? { color } : undefined}
        // a breach pulses like a hazard light — the one non-interactive motion in the rack,
        // reserved for the state that actually needs a second glance
        animate={severity === "breach" ? { opacity: [1, 0.72, 1] } : { opacity: 1 }}
        transition={severity === "breach" ? { duration: 1.6, repeat: Infinity, ease: "easeInOut" } : { duration: 0.3 }}
      >
        {appliance.latest_watts != null ? `${Math.round(appliance.latest_watts)}W` : "—"}
      </motion.div>
      <span className="tnum -mt-1 text-xs text-ink-dim">of {appliance.rated_watts}W rated</span>

      <Sparkline readings={readings} color={color} />
      <span className="text-xs" style={{ color: severity === "normal" ? "var(--ink-dim)" : color }}>
        {LABEL[severity]}
      </span>
    </motion.div>
  );
}
