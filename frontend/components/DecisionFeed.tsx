"use client";

import { useRef } from "react";
import { AnimatePresence } from "motion/react";
import { DecisionRow } from "./DecisionRow";
import type { Decision } from "@/lib/types";

export function DecisionFeed({ decisions, onAcknowledged }: { decisions: Decision[]; onAcknowledged: () => void }) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  if (decisions.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-line px-4 py-8 text-center text-sm text-ink-dim">
        No decisions yet. Fire a scenario above, or let the simulator run for a minute.
      </div>
    );
  }

  return (
    <div ref={scrollerRef} className="flex max-h-[520px] flex-col overflow-y-auto pr-1">
      <AnimatePresence initial={false}>
        {decisions.map((decision) => (
          <DecisionRow
            key={decision.candidate_id}
            decision={decision}
            scrollerRef={scrollerRef}
            onAcknowledged={onAcknowledged}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}
