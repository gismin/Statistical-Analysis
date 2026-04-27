const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export type HealthStatus = {
  status: "ok" | "degraded";
  checks?: Record<string, string>;
};

export const api = {
  health: () => apiFetch<HealthStatus>("/api/health"),
  healthDetailed: () => apiFetch<HealthStatus>("/api/health/detailed"),
};
