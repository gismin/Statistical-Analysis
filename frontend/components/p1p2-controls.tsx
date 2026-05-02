"use client";

import { SYMBOLS, TIMEFRAMES } from "@/lib/api";

export type P1P2ControlsState = {
  symbol: string;
  timeframe: string;
  fromDate: string;
  toDate: string;
};

type Props = {
  value: P1P2ControlsState;
  onChange: (next: P1P2ControlsState) => void;
  showDateRange?: boolean;
};

export function P1P2Controls({ value, onChange, showDateRange = true }: Props) {
  const set = (patch: Partial<P1P2ControlsState>) =>
    onChange({ ...value, ...patch });

  return (
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
  );
}
