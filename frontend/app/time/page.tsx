"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  api,
  SYMBOLS,
  TIMEFRAMES,
  type TimeBucket,
  type TimeStatsResponse,
} from "@/lib/api";

const BUCKET_COUNT = 10;

function BarChart({
  buckets,
  currentBucket,
  label,
}: {
  buckets: TimeBucket[];
  currentBucket: number | undefined;
  label: string;
}) {
  const maxRate = Math.max(...buckets.map((b) => b.reversal_rate ?? 0), 0.01);

  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-muted-foreground uppercase tracking-wide">
        {label}
      </h3>

      {/* Bars */}
      <div className="flex items-end gap-1 h-44 w-full">
        {buckets.map((b) => {
          const rate = b.reversal_rate ?? 0;
          const heightPct = (rate / maxRate) * 100;
          const isCurrent = b.bucket_index === currentBucket;
          const hasData = b.count > 0;

          return (
            <div
              key={b.bucket_index}
              className="flex flex-1 flex-col items-center gap-1"
            >
              <span className="text-[10px] text-muted-foreground">
                {hasData ? `${Math.round(rate * 100)}%` : "–"}
              </span>
              <div className="relative w-full flex items-end" style={{ height: "140px" }}>
                <div
                  className={[
                    "w-full rounded-t transition-all",
                    isCurrent
                      ? "bg-blue-500 ring-2 ring-blue-400 ring-offset-1"
                      : hasData
                      ? "bg-muted-foreground/30 hover:bg-muted-foreground/50"
                      : "bg-muted/20",
                  ].join(" ")}
                  style={{ height: hasData ? `${heightPct}%` : "4px" }}
                  title={
                    hasData
                      ? `${b.bucket}: ${Math.round(rate * 100)}% reversal (n=${b.count})`
                      : `${b.bucket}: no data`
                  }
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* X-axis labels — show every other to avoid crowding */}
      <div className="flex gap-1 mt-1">
        {buckets.map((b) => (
          <div
            key={b.bucket_index}
            className={[
              "flex-1 text-center text-[9px]",
              b.bucket_index === currentBucket
                ? "text-blue-500 font-semibold"
                : "text-muted-foreground",
            ].join(" ")}
          >
            {b.bucket_index % 2 === 0 ? `${b.bucket_index * 10}%` : ""}
          </div>
        ))}
      </div>

      {/* Legend */}
      <p className="mt-2 text-xs text-muted-foreground">
        Bar height = reversal rate (extreme held into next session). Blue = current session bucket.
        n = number of historical sessions in that bucket.
      </p>

      {/* Bucket detail row */}
      <div className="mt-3 grid grid-cols-5 gap-1.5 text-[11px]">
        {buckets.map((b) => (
          <div
            key={b.bucket_index}
            className={[
              "rounded border p-1.5 text-center",
              b.bucket_index === currentBucket
                ? "border-blue-500 bg-blue-500/10 text-blue-400"
                : "border-border text-muted-foreground",
            ].join(" ")}
          >
            <div className="font-medium">{b.bucket}</div>
            <div>
              {b.count > 0
                ? `${Math.round((b.reversal_rate ?? 0) * 100)}% rev`
                : "no data"}
            </div>
            <div className="text-[9px] opacity-60">n={b.count}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

type Tab = "high" | "low";

export default function TimePage() {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [timeframe, setTimeframe] = useState("1d");
  const [activeTab, setActiveTab] = useState<Tab>("high");

  const [data, setData] = useState<TimeStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    api
      .timeStats(symbol, timeframe)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol, timeframe]);

  const cur = data?.current_session;
  const distribution =
    activeTab === "high" ? data?.high_distribution : data?.low_distribution;
  const currentBucket =
    activeTab === "high" ? cur?.high_bucket : cur?.low_bucket;
  const earlyFlag = activeTab === "high" ? cur?.early_high : cur?.early_low;
  const timePct =
    activeTab === "high" ? cur?.high_time_pct : cur?.low_time_pct;

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-4xl px-6 py-12">
        {/* Header */}
        <div className="mb-8 flex items-center gap-4">
          <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
            ← Home
          </Link>
          <div>
            <h1 className="text-2xl font-bold">Time Feature</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              When are session highs & lows typically formed? Reversal probability by time bucket.
            </p>
          </div>
        </div>

        {/* Selectors */}
        <div className="mb-6 flex flex-wrap gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Symbol</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {SYMBOLS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground">Timeframe</label>
            <div className="flex rounded-md border border-border overflow-hidden">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={[
                    "px-4 py-1.5 text-sm transition-colors",
                    tf === timeframe
                      ? "bg-foreground text-background"
                      : "bg-background text-foreground hover:bg-muted",
                  ].join(" ")}
                >
                  {tf.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Loading / error states */}
        {loading && (
          <div className="flex items-center gap-2 py-12 text-muted-foreground">
            <div className="h-4 w-4 rounded-full border-2 border-current border-t-transparent animate-spin" />
            Loading stats…
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            {error.includes("404")
              ? "No stats found. Run the ingest pipeline first: python -m scripts.ingest"
              : error}
          </div>
        )}

        {data && !loading && (
          <>
            {/* Current session card */}
            {cur && (
              <div className="mb-6 rounded-xl border bg-card p-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Current Session</p>
                    <p className="text-sm font-semibold">
                      {symbol} · {timeframe.toUpperCase()} · {cur.elapsed_pct}% elapsed
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      High set at{" "}
                      <span className="font-medium text-foreground">
                        {cur.high_time_pct.toFixed(1)}%
                      </span>{" "}
                      · Low set at{" "}
                      <span className="font-medium text-foreground">
                        {cur.low_time_pct.toFixed(1)}%
                      </span>
                    </p>
                  </div>

                  <div className="flex gap-2 flex-wrap">
                    {cur.early_high && (
                      <span className="rounded-full bg-amber-500/20 border border-amber-500/40 px-3 py-1 text-xs text-amber-400 font-medium">
                        ⚠ Early High
                      </span>
                    )}
                    {cur.early_low && (
                      <span className="rounded-full bg-amber-500/20 border border-amber-500/40 px-3 py-1 text-xs text-amber-400 font-medium">
                        ⚠ Early Low
                      </span>
                    )}
                    {!cur.early_high && !cur.early_low && (
                      <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
                        No early extreme
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Tab switcher */}
            <div className="mb-4 flex gap-1 rounded-lg border border-border p-1 w-fit">
              {(["high", "low"] as Tab[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setActiveTab(t)}
                  className={[
                    "rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
                    t === activeTab
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:text-foreground",
                  ].join(" ")}
                >
                  {t === "high" ? "High Distribution" : "Low Distribution"}
                </button>
              ))}
            </div>

            {/* Context line for current bucket */}
            {cur && distribution && currentBucket !== undefined && (
              <div className="mb-4 rounded-lg border border-border bg-card px-4 py-2 text-sm">
                Current {activeTab} is in bucket{" "}
                <span className="font-semibold text-blue-400">
                  {distribution[currentBucket]?.bucket}
                </span>
                {distribution[currentBucket]?.reversal_rate != null && (
                  <>
                    {" "}—{" "}
                    <span className="font-semibold">
                      {Math.round(
                        (distribution[currentBucket]?.reversal_rate ?? 0) * 100
                      )}
                      % reversal rate
                    </span>{" "}
                    historically (
                    {distribution[currentBucket]?.count} sessions)
                  </>
                )}
                {earlyFlag && (
                  <span className="ml-2 text-amber-400 font-medium">
                    · Unusually early — high reversal probability
                  </span>
                )}
              </div>
            )}

            {/* Chart */}
            {distribution && (
              <div className="rounded-xl border bg-card p-6">
                <BarChart
                  buckets={distribution}
                  currentBucket={currentBucket}
                  label={`${activeTab === "high" ? "High" : "Low"} reversal rate by time bucket — ${symbol} ${timeframe.toUpperCase()}`}
                />
              </div>
            )}

            {/* Footer stats */}
            <p className="mt-4 text-xs text-muted-foreground">
              Based on {data.total_sessions} historical sessions · Stats cached 15 min
            </p>
          </>
        )}
      </div>
    </main>
  );
}
