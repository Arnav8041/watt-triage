import type { Appliance, Decision, Reading, Scenario } from "./types";

function baseUrl() {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${baseUrl()}${path}`, { cache: "no-store" });
  if (!response.ok) throw new ApiError(`${path} failed`, response.status);
  return response.json();
}

async function post<T>(path: string): Promise<T> {
  const response = await fetch(`${baseUrl()}${path}`, { method: "POST", cache: "no-store" });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail ?? `${path} failed`, response.status);
  }
  return response.json();
}

export function getAppliances() {
  return get<Appliance[]>("/appliances");
}

export function getReadings(applianceId: string, minutes: number) {
  return get<Reading[]>(`/appliances/${applianceId}/readings?minutes=${minutes}`);
}

export function getDecisions(limit = 20) {
  return get<Decision[]>(`/decisions?limit=${limit}`);
}

export function acknowledgeDecision(decisionId: number) {
  return post<{ id: number; acknowledged_at: string }>(`/decisions/${decisionId}/acknowledge`);
}

export function fireScenario(scenario: Scenario) {
  return post<{ scenario: string }>(`/admin/fire/${scenario}`);
}

export { ApiError };
