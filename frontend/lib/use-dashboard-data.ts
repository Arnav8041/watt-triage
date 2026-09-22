"use client";

import useSWR from "swr";
import { getAppliances, getDecisions, getReadings } from "./api";
import type { Reading } from "./types";

const POLL_MS = 2000;
const TRACE_MINUTES = 10; // enough sparkline history at the simulator's ~5s cadence

export function useDashboardData() {
  const appliancesQuery = useSWR("appliances", getAppliances, { refreshInterval: POLL_MS });
  const decisionsQuery = useSWR("decisions", () => getDecisions(30), { refreshInterval: POLL_MS });

  const applianceIds = appliancesQuery.data?.map((a) => a.id) ?? [];
  const tracesQuery = useSWR(
    applianceIds.length ? ["traces", applianceIds.join(",")] : null,
    async () => {
      const entries = await Promise.all(
        applianceIds.map(async (id) => [id, await getReadings(id, TRACE_MINUTES)] as const),
      );
      return Object.fromEntries(entries) as Record<string, Reading[]>;
    },
    { refreshInterval: POLL_MS },
  );

  function refresh() {
    appliancesQuery.mutate();
    decisionsQuery.mutate();
    tracesQuery.mutate();
  }

  return {
    appliances: appliancesQuery.data ?? null,
    traces: tracesQuery.data ?? {},
    decisions: decisionsQuery.data ?? null,
    error: appliancesQuery.error || decisionsQuery.error ? "Can't reach the WattTriage API." : null,
    refresh,
  };
}
