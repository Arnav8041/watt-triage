"use client";

import { motion } from "motion/react";
import { ApplianceCard } from "./ApplianceCard";
import type { Appliance, Reading } from "@/lib/types";

// staggers each column's entrance — the one orchestrated page-load moment: the whole
// rack switching on, left to right, rather than five things fading in independently
const container = { hidden: {}, visible: { transition: { staggerChildren: 0.08 } } };

// one continuous bench of gauges, not five separate floating cards — a divider rule
// between columns instead of a border around each, because these are readouts on the
// same panel, not independent widgets
export function ApplianceStrip({
  appliances,
  traces,
}: {
  appliances: Appliance[];
  traces: Record<string, Reading[]>;
}) {
  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="visible"
      className="flex flex-col divide-y divide-line rounded-md border border-line bg-surface sm:flex-row sm:divide-x sm:divide-y-0"
    >
      {appliances.map((appliance) => (
        <ApplianceCard key={appliance.id} appliance={appliance} readings={traces[appliance.id] ?? []} />
      ))}
    </motion.div>
  );
}
