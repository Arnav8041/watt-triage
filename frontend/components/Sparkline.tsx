"use client";

import { motion } from "motion/react";
import type { Reading } from "@/lib/types";

// draws in like a trace appearing on a scope, once, when the card first mounts with
// real data — variant names ("hidden"/"visible") match ApplianceCard's so this
// inherits its entrance timing instead of running on its own clock
const line = { hidden: { pathLength: 0 }, visible: { pathLength: 1, transition: { duration: 0.8, ease: "easeOut" as const } } };
const area = { hidden: { fillOpacity: 0 }, visible: { fillOpacity: 0.14, transition: { duration: 0.8, delay: 0.15 } } };

export function Sparkline({ readings, color }: { readings: Reading[]; color: string }) {
  if (readings.length < 2) {
    return <div className="h-12 w-full" aria-hidden />;
  }
  const watts = readings.map((r) => r.watts);
  const min = Math.min(...watts);
  const max = Math.max(...watts);
  const span = max - min || 1;
  const coords = watts.map((w, i) => {
    const x = (i / (watts.length - 1)) * 100;
    const y = 44 - ((w - min) / span) * 38;
    return [x, y] as const;
  });
  const linePoints = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const areaPoints = `0,44 ${linePoints} 100,44`;

  return (
    <svg viewBox="0 0 100 44" preserveAspectRatio="none" className="h-12 w-full" aria-hidden>
      <motion.polygon points={areaPoints} fill={color} variants={area} />
      <motion.polyline
        points={linePoints}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        variants={line}
      />
    </svg>
  );
}
