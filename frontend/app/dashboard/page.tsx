"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ApplianceStrip } from "@/components/ApplianceStrip";
import { DecisionFeed } from "@/components/DecisionFeed";
import { FireControl } from "@/components/FireControl";
import { MeterRackSkeleton } from "@/components/MeterRackSkeleton";
import { useDashboardData } from "@/lib/use-dashboard-data";
import { severityOf } from "@/lib/severity";

export default function DashboardPage() {
  const { appliances, traces, decisions, error, refresh } = useDashboardData();
  const loading = appliances === null || decisions === null;
  const hotCount = appliances?.filter((a) => severityOf(a) !== "normal").length ?? 0;
  // see app/page.tsx: MotionConfig doesn't neutralize opacity-keyframe flickers, so this
  // needs its own explicit check too
  const reduceMotion = useReducedMotion();

  return (
    <main className="min-h-full bg-bg text-ink">
      <div className="mx-auto flex max-w-5xl flex-col gap-8 px-4 py-8">
        <nav className="flex items-center justify-between">
          <Link href="/" className="text-sm text-ink-dim transition-colors hover:text-ink">
            {/* the same signature flicker as the landing page's wordmark, scaled down —
                this page is switching on too, not just the home page */}
            ← <motion.span
              initial={{ opacity: 0 }}
              animate={reduceMotion ? { opacity: 1 } : { opacity: [0, 1, 0.2, 1, 0.4, 1] }}
              transition={
                reduceMotion
                  ? { duration: 0.2 }
                  : { duration: 0.6, times: [0, 0.15, 0.3, 0.45, 0.6, 1], ease: "easeInOut" }
              }
            >
              WattTriage
            </motion.span>
          </Link>
          <span
            className="tnum rounded-full border px-3 py-1 text-xs"
            style={{
              borderColor: loading ? "var(--line)" : hotCount > 0 ? "var(--hot)" : "var(--safe)",
              color: loading ? "var(--ink-dim)" : hotCount > 0 ? "var(--hot)" : "var(--safe)",
            }}
          >
            {loading ? "Connecting…" : hotCount > 0 ? `${hotCount} running hot` : "Fleet normal"}
          </span>
        </nav>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, duration: 0.4 }}>
          <h1 className="text-2xl font-bold tracking-tight">Live dashboard</h1>
          <p className="mt-1 max-w-xl text-sm text-ink-dim">
            Five real appliances, reporting real wattage. The rack below updates every couple of seconds — nothing
            on this page is a mockup.
          </p>
        </motion.div>

        {error && <div className="rounded-md border border-breach/40 bg-surface px-3 py-2 text-xs text-breach">{error}</div>}

        {loading ? <MeterRackSkeleton /> : <ApplianceStrip appliances={appliances} traces={traces} />}

        <div className="flex flex-col gap-3 border-t border-line pt-6">
          <p className="text-sm text-ink-dim">
            <span className="font-medium text-ink">Try it:</span> fire a fault below and watch the agent investigate
            it in the decision log — usually within a few seconds.
          </p>
          <FireControl onFired={refresh} />
        </div>

        <section className="flex flex-col gap-3 border-t border-line pt-6">
          <div>
            <h2 className="text-sm font-medium text-ink">Decision log</h2>
            <p className="mt-1 text-sm text-ink-dim">
              Every row is the agent&apos;s own written verdict. Expand one to read its reasoning and see exactly
              which gate rule decided the outcome.
            </p>
          </div>
          {loading ? (
            <div className="h-24 animate-pulse rounded-md border border-line bg-surface" />
          ) : (
            <DecisionFeed decisions={decisions} onAcknowledged={refresh} />
          )}
        </section>
      </div>
    </main>
  );
}
