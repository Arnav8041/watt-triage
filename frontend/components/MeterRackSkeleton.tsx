"use client";

import { motion } from "motion/react";

// mirrors the real rack's shape (one panel, five divided columns) so the swap to live
// data doesn't jump, with a scan sweep instead of static gray blocks — it reads as an
// instrument warming up, not a page still loading
export function MeterRackSkeleton() {
  return (
    <div className="relative overflow-hidden rounded-md border border-line bg-surface">
      <div className="flex flex-col divide-y divide-line sm:flex-row sm:divide-x sm:divide-y-0">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex flex-1 flex-col gap-3 px-4 py-4">
            <div className="h-3 w-16 rounded-sm bg-line" />
            <div className="h-8 w-24 rounded-sm bg-line" />
            <div className="h-12 w-full rounded-sm bg-line/50" />
            <div className="h-3 w-14 rounded-sm bg-line" />
          </div>
        ))}
      </div>
      <motion.div
        className="pointer-events-none absolute inset-y-0 w-1/4"
        style={{ background: "linear-gradient(90deg, transparent, color-mix(in srgb, var(--safe-glow) 22%, transparent), transparent)" }}
        animate={{ left: ["-25%", "100%"] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}
