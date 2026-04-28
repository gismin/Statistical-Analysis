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

export type TimeBucket = {
  bucket: string;          // "0–10%"
  bucket_index: number;    // 0–9
  count: number;
  reversal_count: number;
  reversal_rate: number | null;     // 0–1
  continuation_rate: number | null; // 0–1
};

export type CurrentSession = {
  high_time_pct: number;
  low_time_pct: number;
  high_bucket: number;
  low_bucket: number;
  early_high: boolean;
  early_low: boolean;
  elapsed_pct: number;
  session_start: string;
};

export type TimeStatsResponse = {
  symbol: string;
  timeframe: string;
  total_sessions: number;
  high_distribution: TimeBucket[];
  low_distribution: TimeBucket[];
  current_session: CurrentSession | null;
};

export const SYMBOLS = [
  "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
  "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
] as const;

export type Symbol = (typeof SYMBOLS)[number];

export const TIMEFRAMES = ["1d", "1w"] as const;
export type Timeframe = (typeof TIMEFRAMES)[number];

export type DistanceBucket = {
  bucket: string;           // "0–25%"
  bucket_index: number;     // 0–4
  count: number;
  reversal_count: number;
  reversal_rate: number | null;
  continuation_rate: number | null;
};

export type DistanceCurrentSession = {
  range_atr_pct: number;
  atr14: number;
  current_range: number;
  bucket: number;
  small_range: boolean;
  session_start: string;
};

export type DistanceStatsResponse = {
  symbol: string;
  timeframe: string;
  total_sessions: number;
  distribution: DistanceBucket[];
  small_range_threshold: number;
  current_session: DistanceCurrentSession | null;
};

export const api = {
  health: () => apiFetch<HealthStatus>("/api/health"),
  healthDetailed: () => apiFetch<HealthStatus>("/api/health/detailed"),

  timeStats: (symbol: string, timeframe: string) =>
    apiFetch<TimeStatsResponse>(
      `/api/stats/time?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}`
    ),

  distanceStats: (symbol: string, timeframe: string) =>
    apiFetch<DistanceStatsResponse>(
      `/api/stats/distance?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}`
    ),
};
