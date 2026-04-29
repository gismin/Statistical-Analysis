"""
Pure P1/P2 market structure detection.

No I/O — all inputs are plain Python objects. Safe to unit-test without a DB.

Definitions
-----------
P1   : The *first* price extreme that forms from the candle's open.
       Determined by scanning sub-candles (e.g. hourly candles inside a weekly
       candle) and finding the first sub-candle that breaks either above or below
       the candle's open price.

P2   : The *ultimate* opposite extreme of the candle (the candle's high if P1
       was the low, or the candle's low if P1 was the high).  P2 time = the
       first sub-candle where that ultimate opposite extreme was printed.

Flip : After P1 forms, a new extreme is made in the *same* direction as P1
       (P1 is "invalidated").  Each new lower-low after a P1=low, or new
       higher-high after a P1=high, increments flip_count by one.

       After all flips, final_p1_price equals the candle's ultimate extreme in
       P1's direction (i.e. the candle's low if P1=low, its high if P1=high).

Flags
-----
low_held  : P1 was the low AND no flip occurred — the low was the final low.
high_held : P1 was the high AND no flip occurred — the high was the final high.
            These flags are used to filter "confidence target" samples.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SubCandle:
    """One sub-period candle (e.g. 1-hour bar inside a weekly candle)."""
    open_time: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass
class P1P2Result:
    # Original P1 — first extreme to form
    p1_side: str            # "low" | "high"
    p1_price: float
    p1_time: datetime
    p1_dist_pct: float      # (p1_price − open) / open × 100  →  negative for lows
    p1_time_pct: float      # 0–100: % of candle period elapsed when original P1 formed

    # Flip tracking
    p1_flip_count: int      # 0 = clean P1; 1+ = number of P1 resets
    p1_flip_occurred: bool

    # Final P1 after all flips  (== candle's ultimate low/high)
    final_p1_price: float
    final_p1_time: datetime
    final_p1_dist_pct: float
    final_p1_time_pct: float

    # P2 — ultimate opposite extreme; time = first sub-candle it was printed
    p2_price: float
    p2_time: datetime
    p2_dist_pct: float
    p2_time_pct: float      # 0–100: % of candle period elapsed when P2 first printed

    # Convenience flags (pre-computed for fast DB filtering)
    is_bullish: bool        # close > open
    low_held: bool          # p1_side == "low" AND flip_count == 0
    high_held: bool         # p1_side == "high" AND flip_count == 0

    # Data quality
    sub_candle_count: int


# ── Timeframe helpers ──────────────────────────────────────────────────────────

_TF_DELTA: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
}


def candle_close_time(open_time: datetime, timeframe: str) -> datetime:
    """
    Return the exclusive close timestamp of a candle (= next candle's open).

    For "1mo", advances to the first day of the following calendar month.
    Supported timeframes: "1h", "4h", "1d", "1w", "1mo".
    """
    if timeframe in _TF_DELTA:
        return open_time + _TF_DELTA[timeframe]
    if timeframe == "1mo":
        y, m = open_time.year, open_time.month
        if m == 12:
            return open_time.replace(year=y + 1, month=1, day=1,
                                     hour=0, minute=0, second=0, microsecond=0)
        return open_time.replace(month=m + 1, day=1,
                                 hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"Unsupported timeframe: {timeframe!r}")


# ── Core detection ─────────────────────────────────────────────────────────────

def detect_p1_p2(
    open_price: float,
    high: float,        # noqa: ARG001 — kept for caller convenience / future use
    low: float,         # noqa: ARG001
    close: float,
    candle_open_time: datetime,
    timeframe: str,
    sub_candles: list[SubCandle],
) -> P1P2Result | None:
    """
    Detect P1/P2 market structure for a single *completed* candle.

    Parameters
    ----------
    open_price       : Candle open price.
    high / low       : Candle ultimate high and low (accepted but derived from
                       sub-candles internally — provided for validation purposes).
    close            : Candle close price.
    candle_open_time : UTC timestamp of the candle's open.
    timeframe        : One of "1h", "4h", "1d", "1w", "1mo".
    sub_candles      : Intra-candle bars, sorted ascending by open_time,
                       all falling within [candle_open_time, candle_close_time).

    Returns
    -------
    P1P2Result on success, None if sub_candles is empty or price never
    departed from the open (degenerate / zero-range data).
    """
    if not sub_candles:
        return None

    sub_count = len(sub_candles)
    close_time = candle_close_time(candle_open_time, timeframe)
    duration_s = (close_time - candle_open_time).total_seconds()
    if duration_s <= 0:
        return None

    # ── Shared helpers ─────────────────────────────────────────────────────────

    def _time_pct(t: datetime) -> float:
        """% of candle period elapsed at timestamp t (clamped 0–100)."""
        elapsed = (t - candle_open_time).total_seconds()
        return round(min(100.0, max(0.0, elapsed / duration_s * 100)), 2)

    def _dist_pct(price: float) -> float:
        """% distance from open (negative = below open)."""
        return round((price - open_price) / open_price * 100, 4)

    # ── Step 1: Find P1 (first direction price departs from open) ──────────────
    #
    # Scan sub-candles chronologically.  The moment a sub-candle breaks either
    # above or below the candle's open price, that determines P1's direction.
    #
    # Edge case — both extremes in the same sub-candle (e.g. a large opening
    # bar): take the larger absolute distance from open as P1.

    p1_side: str | None = None
    p1_price: float | None = None
    p1_candle: SubCandle | None = None
    p1_idx: int | None = None

    for i, sub in enumerate(sub_candles):
        above = sub.high > open_price
        below = sub.low < open_price

        if above and below:
            # Both extremes in one bar — tiebreak by larger absolute move
            if (sub.high - open_price) >= (open_price - sub.low):
                p1_side, p1_price = "high", sub.high
            else:
                p1_side, p1_price = "low", sub.low
            p1_candle, p1_idx = sub, i
            break
        elif above:
            p1_side, p1_price = "high", sub.high
            p1_candle, p1_idx = sub, i
            break
        elif below:
            p1_side, p1_price = "low", sub.low
            p1_candle, p1_idx = sub, i
            break

    if p1_side is None or p1_candle is None or p1_idx is None or p1_price is None:
        return None  # price never moved from open — degenerate data

    # ── Step 2: Scan remaining sub-candles for flips ───────────────────────────
    #
    # A flip occurs each time a new extreme in P1's direction is reached after
    # the original P1 formed.  We track every reset so flip_count can be used
    # to distinguish single-flip from double-flip candles.

    flip_count = 0
    cur_p1_price = p1_price
    cur_p1_candle = p1_candle

    for sub in sub_candles[p1_idx + 1:]:
        if p1_side == "low" and sub.low < cur_p1_price:
            flip_count += 1
            cur_p1_price = sub.low
            cur_p1_candle = sub
        elif p1_side == "high" and sub.high > cur_p1_price:
            flip_count += 1
            cur_p1_price = sub.high
            cur_p1_candle = sub

    # ── Step 3: Locate P2 (ultimate opposite extreme, first occurrence) ────────
    #
    # P2 price   = the candle's ultimate extreme in the opposite direction.
    # P2 time    = the first sub-candle where that ultimate price was touched.
    #
    # Scanning through sub_candles (not sub_candles[p1_idx:]) so that P2 time
    # reflects the true first occurrence within the whole candle period.

    if p1_side == "low":
        p2_price = max(s.high for s in sub_candles)
        p2_candle = next(s for s in sub_candles if s.high >= p2_price)
    else:
        p2_price = min(s.low for s in sub_candles)
        p2_candle = next(s for s in sub_candles if s.low <= p2_price)

    # ── Step 4: Derived flags ──────────────────────────────────────────────────

    is_bullish = close > open_price
    low_held = p1_side == "low" and flip_count == 0
    high_held = p1_side == "high" and flip_count == 0

    return P1P2Result(
        p1_side=p1_side,
        p1_price=p1_price,
        p1_time=p1_candle.open_time,
        p1_dist_pct=_dist_pct(p1_price),
        p1_time_pct=_time_pct(p1_candle.open_time),
        p1_flip_count=flip_count,
        p1_flip_occurred=flip_count > 0,
        final_p1_price=cur_p1_price,
        final_p1_time=cur_p1_candle.open_time,
        final_p1_dist_pct=_dist_pct(cur_p1_price),
        final_p1_time_pct=_time_pct(cur_p1_candle.open_time),
        p2_price=p2_price,
        p2_time=p2_candle.open_time,
        p2_dist_pct=_dist_pct(p2_price),
        p2_time_pct=_time_pct(p2_candle.open_time),
        is_bullish=is_bullish,
        low_held=low_held,
        high_held=high_held,
        sub_candle_count=sub_count,
    )
