"use client";

import { SYMBOLS, TIMEFRAMES } from "@/lib/api";

export type P1P2ControlsState = {
  symbol: string;
  timeframe: string;
  fromDate: string;
  toDate: string;
  weekdays: number[]; // [] = all; [0,1,2,3,4] = Mon–Fri; etc.
};

// 0 = Mon … 6 = Sun (matches Python weekday())
const DAY_LABELS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];
const ALL_DAYS = [0, 1, 2, 3, 4, 5, 6];
const WEEKDAYS = [0, 1, 2, 3, 4];

type Props = {
  value: P1P2ControlsState;
  onChange: (next: P1P2ControlsState) => void;
  showDateRange?: boolean;
  showWeekdays?: boolean;
};

export function P1P2Controls({
  value,
  onChange,
  showDateRange = true,
  showWeekdays = true,
}: Props) {
  const set = (patch: Partial<P1P2ControlsState>) =>
    onChange({ ...value, ...patch });

  function toggleDay(d: number) {
    const current = value.weekdays.length === 0 ? ALL_DAYS : value.weekdays;
    const next = current.includes(d)
      ? current.filter((x) => x !== d)
      : [...current, d].sort();
    // If all 7 selected, treat as "no filter"
    set({ weekdays: next.length === 7 ? [] : next });
  }

  function isActive(d: number) {
    return value.weekdays.length === 0 || value.weekdays.includes(d);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-4">
        {/* Symbol */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Symbol</label>
          <select
            value={value.symbol}
            onChange={(e) => set({ symbol: e.target.value })}
            className="rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {SYMBOLS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* Timeframe */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground">Timeframe</label>
          <div className="flex rounded-md border border-border overflow-hidden">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => set({ timeframe: tf })}
                className={[
                  "px-4 py-1.5 text-sm transition-colors",
                  tf === value.timeframe
                    ? "bg-foreground text-background"
                    : "bg-background text-foreground hover:bg-muted",
                ].join(" ")}
              >
                {tf.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Date range */}
        {showDateRange && (
          <>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">From</label>
              <input
                type="date"
                value={value.fromDate}
                onChange={(e) => set({ fromDate: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-muted-foreground">To</label>
              <input
                type="date"
                value={value.toDate}
                onChange={(e) => set({ toDate: e.target.value })}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </>
        )}
      </div>

      {/* Weekday filter */}
      {showWeekdays && (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs text-muted-foreground">Days:</span>

          {/* Preset buttons */}
          <button
            onClick={() => set({ weekdays: [] })}
            className={[
              "rounded-md px-2.5 py-1 text-xs font-medium border transition-colors",
              value.weekdays.length === 0
                ? "bg-foreground text-background border-foreground"
                : "border-border text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            All
          </button>
          <button
            onClick={() => set({ weekdays: WEEKDAYS })}
            className={[
              "rounded-md px-2.5 py-1 text-xs font-medium border transition-colors",
              JSON.stringify(value.weekdays) === JSON.stringify(WEEKDAYS)
                ? "bg-foreground text-background border-foreground"
                : "border-border text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            Mon–Fri
          </button>

          {/* Individual day toggles */}
          <div className="flex gap-1">
            {DAY_LABELS.map((label, i) => (
              <button
                key={i}
                onClick={() => toggleDay(i)}
                className={[
                  "w-8 h-7 rounded text-xs font-medium border transition-colors",
                  isActive(i)
                    ? i >= 5
                      ? "bg-amber-500/20 border-amber-500/40 text-amber-400"
                      : "bg-blue-500/20 border-blue-500/40 text-blue-400"
                    : "border-border text-muted-foreground/40",
                ].join(" ")}
                title={["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][i]}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
