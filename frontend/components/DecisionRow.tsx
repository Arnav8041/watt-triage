"use client";

import { useState, type MouseEvent, type RefObject } from "react";
import { motion, AnimatePresence } from "motion/react";
import { GateChecklist } from "./GateChecklist";
import { ToolTrace } from "./ToolTrace";
import { acknowledgeDecision } from "@/lib/api";
import { EXPAND_TRANSITION_SECONDS } from "@/lib/motion-constants";
import type { Decision } from "@/lib/types";

const OUTCOME_COLOR = { pending: "var(--pending)", escalated: "var(--breach)", resolved: "var(--safe)" };
const OUTCOME_LABEL = { pending: "Investigating", escalated: "Escalation", resolved: "Quiet resolution" };

export function DecisionRow({
  decision,
  scrollerRef,
  onAcknowledged,
}: {
  decision: Decision;
  scrollerRef: RefObject<HTMLDivElement | null>;
  onAcknowledged: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [acking, setAcking] = useState(false);
  const color = OUTCOME_COLOR[decision.outcome];
  const canExpand = decision.outcome !== "pending";
  const isEscalated = decision.outcome === "escalated";
  const needsAck = isEscalated && !decision.acknowledged_at;
  const acknowledged = isEscalated && !!decision.acknowledged_at;

  async function acknowledge(event: MouseEvent) {
    event.stopPropagation();
    if (decision.id == null) return;
    setAcking(true);
    try {
      await acknowledgeDecision(decision.id);
      onAcknowledged();
    } finally {
      setAcking(false);
    }
  }

  return (
    // the same row instance carries a Candidate from pending through to its Decision —
    // `layout` settles its position, `animate` on borderColor is the moment it "lands".
    // The left rail is the log's spine: a node per entry, colored by outcome.
    <motion.div layout initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="grid min-w-0 grid-cols-[28px_1fr]">
      <div className="relative flex justify-center" aria-hidden>
        <span className="absolute inset-y-0 w-px bg-line" />
        <span className="relative z-10 mt-5 h-2.5 w-2.5 rounded-full ring-4 ring-surface" style={{ background: color }} />
      </div>

      <motion.div
        layout
        animate={{ borderColor: color }}
        transition={{ layout: { type: "spring", stiffness: 400, damping: 30 }, borderColor: { duration: 0.4 } }}
        className="mb-3 min-w-0 rounded-md border bg-surface-raised"
      >
        <button
          type="button"
          onClick={() => canExpand && setExpanded((v) => !v)}
          className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-left disabled:cursor-default"
          aria-expanded={expanded}
          disabled={!canExpand}
        >
          <span className="tnum text-xs text-ink-dim">
            {new Date(decision.decided_at ?? decision.detected_at).toLocaleTimeString()}
          </span>
          <span className="text-sm text-ink">{decision.appliance_id}</span>
          <span className="tnum text-sm text-ink-dim">{Math.round(decision.watts)}W</span>
          <span className="text-xs font-medium" style={{ color }}>
            {OUTCOME_LABEL[decision.outcome]}
          </span>
          {needsAck && (
            <motion.span
              layout
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="rounded-full px-2 py-0.5 text-[11px]"
              style={{ background: `color-mix(in srgb, ${color} 18%, transparent)`, color }}
            >
              unacknowledged
            </motion.span>
          )}
          {acknowledged && (
            <motion.span
              layout
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="rounded-full px-2 py-0.5 text-[11px]"
              style={{ background: "color-mix(in srgb, var(--safe) 18%, transparent)", color: "var(--safe)" }}
            >
              ✓ acknowledged
            </motion.span>
          )}
          {decision.reasoning && (
            <span className="min-w-0 basis-full truncate text-xs text-ink-dim sm:ml-auto sm:max-w-xs sm:flex-1 sm:basis-auto">
              {decision.reasoning}
            </span>
          )}
          {canExpand && <span className="text-ink-dim">{expanded ? "−" : "+"}</span>}
        </button>

        <AnimatePresence initial={false}>
          {expanded && (
            <motion.div
              key="body"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: EXPAND_TRANSITION_SECONDS, ease: "easeOut" }}
              className="overflow-hidden border-t border-line px-3 py-3"
            >
              <p className="prose-log mb-3 text-ink">{decision.reasoning}</p>
              {decision.gate_reason && (
                <p className="mb-3 text-xs text-ink-dim">
                  Gate reason: <span className="text-ink">{decision.gate_reason}</span>
                </p>
              )}
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <h4 className="mb-1 text-xs text-ink-dim">Gate checklist</h4>
                  <GateChecklist decision={decision} />
                </div>
                <div>
                  <h4 className="mb-1 text-xs text-ink-dim">Tool-call trace</h4>
                  {decision.tool_trace && decision.tool_trace.length > 0 ? (
                    <ToolTrace trace={decision.tool_trace} scrollerRef={scrollerRef} />
                  ) : (
                    <p className="text-xs text-ink-dim">No tool calls recorded.</p>
                  )}
                </div>
              </div>
              {needsAck && (
                <button
                  type="button"
                  onClick={acknowledge}
                  disabled={acking}
                  className="mt-3 cursor-pointer rounded border px-3 py-1 text-xs disabled:cursor-default disabled:opacity-60"
                  style={{ borderColor: "var(--breach)", color: "var(--breach)" }}
                >
                  {acking ? "Acknowledging…" : "Acknowledge"}
                </button>
              )}
              {acknowledged && decision.acknowledged_at && (
                <p className="mt-3 text-xs" style={{ color: "var(--safe)" }}>
                  ✓ Acknowledged at {new Date(decision.acknowledged_at).toLocaleTimeString()}
                </p>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
}
