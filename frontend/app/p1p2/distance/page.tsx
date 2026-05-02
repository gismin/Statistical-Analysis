"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type P1P2ConfidenceResponse, type ConfidenceTarget } from "@/lib/api";
import { P1P2Controls, type P1P2ControlsState } from "@/components/p1p2-controls";
import { UtcClock } from "@/components/utc-clock";

// ── Confidence table ───────────────────────────────────────────────────────────

function TargetRow({
  t,
  direction,
}: {
  t: ConfidenceTarget;
  direction: "long" | "short";
}) {
  const isHigh = t.confidence >= 80;
  return (
    <tr
      className={[
        "border-b border-border text-sm",
        isHigh ? "font-semibold" : "",
      ].join(" ")}
    >
      <td className="py-2.5 pr-4 text-muted-foreground">
        <span
          className={[
            "inline-block w-10 text-center rounded-full text-xs py-0.5",
            t.confidence >= 80
              ? "bg-blue-500/20 text-blue-400"
              : "bg-muted text-muted-foreground",
          ].join(" ")}
        >
          {t.confidence}%
        </span>
      </td>
      <td className="py-2.5 pr-4 tabular-nums">{t.dist_pct.toFixed(2)}%</td>
      <td
        className={[
          "py-2.5 tabular-nums",
          direction === "long" ? "text-green-400" : "text-red-400",
        ].join(" ")}
      >
        {t.price.toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}
      </td>
    </tr>
  );
}

function TargetTable({
  title,
  targets,
  direction,
  empty,
}: {
  title: string;
  targets: ConfidenceTarget[];
  direction: "long" | "short";
  empty: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-5 flex-1 min-w-[240px]">
      <p
        className={[
          "text-xs font-semibold uppercase tracking-wide mb-4",
          direction === "long" ? "text-green-400" : "text-red-400",
        ].join(" ")}
      >
        {title}
      </p>

      {targets.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <>
          <table className="w-full">
            <thead>
              <tr className="text-[11px] text-muted-foreground border-b border-border">
                <th className="pb-2 pr-4 text-left font-medium">Confidence</th>
                <th className="pb-2 pr-4 text-left font-medium">Move %</th>
                <th className="pb-2 text-left font-medium">Target price</th>
              </tr>
            </thead>
            <tbody>
              {targets.map((t) => (
                <TargetRow key={t.confidence} t={t} direction={direction} />
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-[11px] text-muted-foreground">
            n = {targets[0]?.sample_size} qualifying sessions
          </p>
        </>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function P1P2DistancePage() {
  const [controls, setControls] = useState<P1P2ControlsState>({
    symbol: "BTC/USDT",
    timeframe: "1w",
    fromDate: "",
    toDate: "",
  });

  const [openPrice, setOpenPrice] = useState<number>(0);

  const [data, setData] = useState<P1P2ConfidenceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    if (!openPrice || openPrice <= 0) {
      setError("Enter a valid open price > 0");
      return;
    }
    setLoading(true);
    setError(null);
    setData(null);
    api
      .p1p2ConfidenceTargets({
        symbol: controls.symbol,
        timeframe: controls.timeframe,
        open_price: openPrice,
        from_date: controls.fromDate || undefined,
        to_date: controls.toDate || undefined,
      })
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-4xl px-6 py-12">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
              ← Home
            </Link>
            <div>
              <h1 className="text-2xl font-bold">Confidence Targets</h1>
              <p className="text-sm text-muted-foreground mt-0.5">
                Long & short price targets at 90/80/70/60/50% confidence
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/p1p2/summary"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              ← P1/P2 Summary
            </Link>
            <UtcClock />
          </div>
        </div>

        {/* Controls */}
        <P1P2Controls value={controls} onChange={setControls} />

        {/* Open price input */}
        <div className="mt-5 rounded-xl border bg-card p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-4">
            Current Candle Open Price
          </p>
          <div className="flex items-end gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">
                Open price ({controls.symbol.split("/")[1]})
              </label>
              <input
                type="number"
                value={openPrice || ""}
                min={0}
                step={0.01}
                placeholder="e.g. 65000"
                onChange={(e) => setOpenPrice(parseFloat(e.target.value) || 0)}
                className="w-40 rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring tabular-nums"
              />
            </div>
            <button
              onClick={load}
              disabled={loading}
              className="rounded-md bg-foreground text-background px-5 py-2 text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {loading ? "Loading…" : "Calculate Targets"}
            </button>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Long targets = sessions where the P1 low held. Short targets = sessions where the P1 high held.
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="mt-4 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            {error.includes("404")
              ? "No P1/P2 data found. Run: python -m scripts.ingest --compute-p1p2"
              : error}
          </div>
        )}

        {/* Results */}
        {data && (
          <div className="mt-6 flex flex-col gap-4">
            {/* Open price confirmation */}
            <div className="rounded-lg border border-border bg-card px-4 py-3 text-sm">
              <span className="text-muted-foreground">Open price: </span>
              <span className="font-semibold tabular-nums">
                {data.open_price.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}{" "}
                {data.symbol.split("/")[1]}
              </span>
              <span className="text-muted-foreground mx-2">·</span>
              <span className="text-muted-foreground">
                {data.symbol} · {data.timeframe.toUpperCase()}
              </span>
            </div>

            {/* Target tables */}
            <div className="flex flex-wrap gap-4">
              <TargetTable
                title="Long targets — if P1 low holds"
                targets={data.long_targets}
                direction="long"
                empty="Insufficient sessions where low held (need ≥2)"
              />
              <TargetTable
                title="Short targets — if P1 high holds"
                targets={data.short_targets}
                direction="short"
                empty="Insufficient sessions where high held (need ≥2)"
              />
            </div>

            {/* How to read */}
            <div className="rounded-lg border border-border bg-card p-4 text-xs text-muted-foreground space-y-1">
              <p className="font-medium text-foreground mb-1">How to read</p>
              <p>
                <span className="text-foreground font-medium">90% confidence</span> — 90% of qualifying sessions reached
                this level or further.
              </p>
              <p>
                <span className="text-foreground font-medium">50% confidence</span> — The median move; half of sessions
                reached this level.
              </p>
              <p>Use higher-confidence levels as conservative targets and 50–60% as extended targets.</p>
            </div>

            {/* Data quality */}
            <p
              className={[
                "text-xs",
                data.data_quality.reliable ? "text-muted-foreground" : "text-amber-400",
              ].join(" ")}
            >
              {data.data_quality.message}
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
