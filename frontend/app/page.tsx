"use client";

import { ApplianceStrip } from "@/components/ApplianceStrip";
import { DecisionFeed } from "@/components/DecisionFeed";
import { FireControl } from "@/components/FireControl";
import { useDashboardData } from "@/lib/use-dashboard-data";

export default function Page() {
  const { appliances, traces, decisions, error, refresh } = useDashboardData();
  const loading = appliances === null || decisions === null;

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-medium text-ink">WattTriage</h1>
          <p className="text-xs text-ink-dim">An agent triages every suspicious reading. The gate decides.</p>
        </div>
        <FireControl onFired={refresh} />
      </header>

      {error && (
        <div className="rounded-md border border-danger/40 bg-surface px-3 py-2 text-xs text-danger">{error}</div>
      )}

      {loading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-md border border-line bg-surface" />
          ))}
        </div>
      ) : (
        <>
          <ApplianceStrip appliances={appliances} traces={traces} />
          <section className="flex flex-col gap-2">
            <h2 className="text-xs text-ink-dim">Decisions</h2>
            <DecisionFeed decisions={decisions} onAcknowledged={refresh} />
          </section>
        </>
      )}
    </main>
  );
}
