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

// ── P1/P2 types ───────────────────────────────────────────────────────────────

export type FlipRisk = {
  total: number;
  flipped: number;
  pct: number;
  label: "low" | "moderate" | "high";
};

export type P2LikelihoodTime = {
  pct_formed_by_now: number;
  p2_median_time_pct: number;
  p2_p90_time_pct: number;
  message: string;
};

export type P2LikelihoodDist = {
  pct_moved_further: number;
  current_dist_abs: number;
  p2_median_dist_abs: number;
  message: string;
};

export type Warnings = {
  time_warning: string | null;
  dist_warning: string | null;
  triggered: boolean;
};

export type DataQuality = {
  total: number;
  reliable: boolean;
  message: string;
};

export type P1P2SummaryResponse = {
  flip_risk: FlipRisk;
  p2_likelihood_time: P2LikelihoodTime;
  p2_likelihood_dist: P2LikelihoodDist;
  warnings: Warnings;
  data_quality: DataQuality;
};

export type ConfidenceTarget = {
  confidence: number;
  dist_pct: number;
  price: number;
  sample_size: number;
};

export type P1P2ConfidenceResponse = {
  symbol: string;
  timeframe: string;
  open_price: number;
  long_targets: ConfidenceTarget[];
  short_targets: ConfidenceTarget[];
  data_quality: DataQuality;
};

export type P1P2SummaryParams = {
  symbol: string;
  timeframe: string;
  current_time_pct: number;
  current_p1_dist_abs: number;
  current_p2_dist_abs: number;
  from_date?: string;
  to_date?: string;
  weekdays?: string; // comma-separated "0,1,2,3,4"
};

export type P1P2ConfidenceParams = {
  symbol: string;
  timeframe: string;
  open_price: number;
  from_date?: string;
  to_date?: string;
  weekdays?: string;
};

// ── API client ────────────────────────────────────────────────────────────────

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

  p1p2Summary: (p: P1P2SummaryParams) => {
    const q = new URLSearchParams({
      symbol: p.symbol,
      timeframe: p.timeframe,
      current_time_pct: String(p.current_time_pct),
      current_p1_dist_abs: String(p.current_p1_dist_abs),
      current_p2_dist_abs: String(p.current_p2_dist_abs),
    });
    if (p.from_date) q.set("from_date", p.from_date);
    if (p.to_date) q.set("to_date", p.to_date);
    if (p.weekdays) q.set("weekdays", p.weekdays);
    return apiFetch<P1P2SummaryResponse>(`/api/p1p2/summary?${q}`);
  },

  p1p2ConfidenceTargets: (p: P1P2ConfidenceParams) => {
    const q = new URLSearchParams({
      symbol: p.symbol,
      timeframe: p.timeframe,
      open_price: String(p.open_price),
    });
    if (p.from_date) q.set("from_date", p.from_date);
    if (p.to_date) q.set("to_date", p.to_date);
    if (p.weekdays) q.set("weekdays", p.weekdays);
    return apiFetch<P1P2ConfidenceResponse>(`/api/p1p2/confidence-targets?${q}`);
  },
};
