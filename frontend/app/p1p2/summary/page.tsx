"use client";

import Link from "next/link";
import { useState } from "react";
import {
  api,
  type P1P2SummaryResponse,
  type FlipRisk,
  type Warnings,
} from "@/lib/api";
import { P1P2Controls, type P1P2ControlsState } from "@/components/p1p2-controls";
import { UtcClock } from "@/components/utc-clock";

// ── Small helpers ──────────────────────────────────────────────────────────────

const FLIP_COLOR: Record<FlipRisk["label"], string> = {
  low: "text-green-400",
  moderate: "text-amber-400",
  high: "text-red-400",
};

const FLIP_BG: Record<FlipRisk["label"], string> = {
  low: "border-green-500/40 bg-green-500/10",
  moderate: "border-amber-500/40 bg-amber-500/10",
  high: "border-red-500/40 bg-red-500/10",
};

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div>
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  );
}

function WarningChip({ text }: { text: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs text-amber-400 font-medium">
      ⚠ {text}
    </span>
  );
}

function OkChip({ text }: { text: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-green-500/40 bg-green-500/10 px-3 py-1 text-xs text-green-400 font-medium">
      ✓ {text}
    </span>
  );
}

// ── Input card ─────────────────────────────────────────────────────────────────

function NumInput({
  label,
  hint,
  value,
  onChange,
  min,
  max,
  step,
}: {
  label: string;
  hint: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium">{label}</label>
      <p className="text-[11px] text-muted-foreground">{hint}</p>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step ?? 0.1}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        className="w-28 rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring tabular-nums"
      />
    </div>
  );
}

// ── Summary rows ───────────────────────────────────────────────────────────────

function FlipRiskRow({ d }: { d: P1P2SummaryResponse["flip_risk"] }) {
  return (
    <div className={`rounded-xl border p-5 ${FLIP_BG[d.label]}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
            Row 1 — P1 Flip Risk
          </p>
          <div className="flex flex-wrap gap-8">
            <Stat label="Flip rate" value={`${d.pct}%`} sub={`${d.flipped} / ${d.total} sessions`} />
            <Stat label="Risk level" value={d.label.toUpperCase()} />
          </div>
        </div>
        <span className={`text-3xl font-bold ${FLIP_COLOR[d.label]}`}>
          {d.label === "low" ? "✓" : d.label === "moderate" ? "~" : "!"}
        </span>
      </div>
      {/* Mini progress bar */}
      <div className="mt-4 h-2 rounded-full bg-black/20 overflow-hidden">
        <div
          className={[
            "h-full rounded-full transition-all",
            d.label === "low"
              ? "bg-green-500"
              : d.label === "moderate"
              ? "bg-amber-500"
              : "bg-red-500",
          ].join(" ")}
          style={{ width: `${Math.min(d.pct, 100)}%` }}
        />
      </div>
      <p className="mt-1 text-[10px] text-muted-foreground">
        &lt;30% low · 30–50% moderate · ≥50% high
      </p>
    </div>
  );
}

function P2LikelihoodRow({
  time,
  dist,
}: {
  time: P1P2SummaryResponse["p2_likelihood_time"];
  dist: P1P2SummaryResponse["p2_likelihood_dist"];
}) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-4">
        Row 2 — P2 Likelihood
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {/* Time */}
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs text-muted-foreground mb-3 font-medium">By Time</p>
          <div className="flex gap-6 flex-wrap">
            <Stat
              label="P2 formed by now"
              value={`${time.pct_formed_by_now}%`}
              sub="of sessions"
            />
            <Stat
              label="Median P2 time"
              value={`${time.p2_median_time_pct}%`}
              sub="into candle"
            />
            <Stat
              label="P90 P2 time"
              value={`${time.p2_p90_time_pct}%`}
              sub="90% formed by"
            />
          </div>
          <p className="mt-3 text-xs text-muted-foreground italic">
            {time.message}
          </p>
        </div>

        {/* Distance */}
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs text-muted-foreground mb-3 font-medium">By Distance</p>
          <div className="flex gap-6 flex-wrap">
            <Stat
              label="Moved further"
              value={`${dist.pct_moved_further}%`}
              sub="of sessions"
            />
            <Stat
              label="Median P2 dist"
              value={`${dist.p2_median_dist_abs}%`}
              sub="from open"
            />
          </div>
          <p className="mt-3 text-xs text-muted-foreground italic">
            {dist.message}
          </p>
        </div>
      </div>
    </div>
  );
}

function WarningsRow({ w }: { w: Warnings }) {
  return (
    <div
      className={[
        "rounded-xl border p-5",
        w.triggered
          ? "border-amber-500/40 bg-amber-500/5"
          : "border-green-500/40 bg-green-500/5",
      ].join(" ")}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-4">
        Row 3 — Warnings
      </p>
      <div className="flex flex-wrap gap-2">
        {w.time_warning ? (
          <WarningChip text={w.time_warning} />
        ) : (
          <OkChip text="P1 time is normal" />
        )}
        {w.dist_warning ? (
          <WarningChip text={w.dist_warning} />
        ) : (
          <OkChip text="P1 wick size is normal" />
        )}
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function P1P2SummaryPage() {
  const [controls, setControls] = useState<P1P2ControlsState>({
    symbol: "BTC/USDT",
    timeframe: "1w",
    fromDate: "",
    toDate: "",
  });

  const [timePct, setTimePct] = useState(35);
  const [p1Dist, setP1Dist] = useState(2.5);
  const [p2Dist, setP2Dist] = useState(4.1);

  const [data, setData] = useState<P1P2SummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setLoading(true);
    setError(null);
    setData(null);
    api
      .p1p2Summary({
        symbol: controls.symbol,
        timeframe: controls.timeframe,
        current_time_pct: timePct,
        current_p1_dist_abs: p1Dist,
        current_p2_dist_abs: p2Dist,
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
              <h1 className="text-2xl font-bold">P1/P2 Summary</h1>
              <p className="text-sm text-muted-foreground mt-0.5">
                Flip risk · P2 likelihood · Warnings
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/p1p2/distance"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Confidence Targets →
            </Link>
            <UtcClock />
          </div>
        </div>

        {/* Controls */}
        <P1P2Controls value={controls} onChange={setControls} />

        {/* Current candle inputs */}
        <div className="mt-5 rounded-xl border bg-card p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-4">
            Current Candle Inputs
          </p>
          <div className="flex flex-wrap gap-6">
            <NumInput
              label="Time elapsed %"
              hint="How far into the candle (0–100)"
              value={timePct}
              onChange={setTimePct}
              min={0}
              max={100}
              step={1}
            />
            <NumInput
              label="P1 dist % (abs)"
              hint="First extreme distance from open"
              value={p1Dist}
              onChange={setP1Dist}
              min={0}
              step={0.1}
            />
            <NumInput
              label="P2 dist % (abs)"
              hint="Second extreme distance from open"
              value={p2Dist}
              onChange={setP2Dist}
              min={0}
              step={0.1}
            />
          </div>

          {/* Elapsed slider */}
          <div className="mt-4">
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={timePct}
              onChange={(e) => setTimePct(Number(e.target.value))}
              className="w-full accent-foreground"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
              <span>Candle open</span>
              <span>{timePct}% elapsed</span>
              <span>Candle close</span>
            </div>
          </div>
        </div>

        {/* Load button */}
        <div className="mt-4">
          <button
            onClick={load}
            disabled={loading}
            className="rounded-md bg-foreground text-background px-5 py-2 text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {loading ? "Loading…" : "Load Summary"}
          </button>
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
            <FlipRiskRow d={data.flip_risk} />
            <P2LikelihoodRow time={data.p2_likelihood_time} dist={data.p2_likelihood_dist} />
            <WarningsRow w={data.warnings} />

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
