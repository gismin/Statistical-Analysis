"use client";

import { useEffect, useRef, useState } from "react";

const INTERVALS = [
  { label: "Off", seconds: 0 },
  { label: "30s", seconds: 30 },
  { label: "1m", seconds: 60 },
  { label: "5m", seconds: 300 },
] as const;

type Props = {
  onRefresh: () => void;
  /** Set to true while a fetch is in flight so the timer pauses visually */
  loading?: boolean;
};

export function RefreshTimer({ onRefresh, loading = false }: Props) {
  const [intervalSec, setIntervalSec] = useState(0); // 0 = off
  const [countdown, setCountdown] = useState(0);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Reset and start countdown whenever interval changes
  useEffect(() => {
    if (tickRef.current) clearInterval(tickRef.current);
    if (intervalSec === 0) {
      setCountdown(0);
      return;
    }
    setCountdown(intervalSec);
    tickRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          onRefresh();
          return intervalSec; // reset
        }
        return prev - 1;
      });
    }, 1000);
    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalSec]);

  const pct = intervalSec > 0 ? ((intervalSec - countdown) / intervalSec) * 100 : 0;

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground">Auto-refresh:</span>

      <div className="flex rounded-md border border-border overflow-hidden">
        {INTERVALS.map(({ label, seconds }) => (
          <button
            key={label}
            onClick={() => setIntervalSec(seconds)}
            className={[
              "px-2.5 py-1 text-xs transition-colors",
              seconds === intervalSec
                ? "bg-foreground text-background"
                : "bg-background text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Countdown + ring */}
      {intervalSec > 0 && (
        <div className="flex items-center gap-1.5">
          {/* Mini arc progress */}
          <svg width="18" height="18" viewBox="0 0 18 18" className="-rotate-90">
            <circle
              cx="9" cy="9" r="7"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="text-border"
            />
            <circle
              cx="9" cy="9" r="7"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeDasharray={`${2 * Math.PI * 7}`}
              strokeDashoffset={`${2 * Math.PI * 7 * (1 - pct / 100)}`}
              strokeLinecap="round"
              className={loading ? "text-muted-foreground" : "text-blue-400"}
            />
          </svg>
          <span className="text-xs tabular-nums text-muted-foreground">
            {loading ? "…" : `${countdown}s`}
          </span>
        </div>
      )}
    </div>
  );
}
