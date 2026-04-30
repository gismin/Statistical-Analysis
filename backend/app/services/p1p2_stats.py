"""
P1/P2 statistics service.

Two distinct layers — keep them separate:

  DB layer    async functions that query P1P2Stats rows from PostgreSQL.
  Stats layer pure functions that compute statistics from those rows.
              These can be imported and tested without a running database.

Summary of statistics computed
-------------------------------
flip_risk            % of sessions where P1 was invalidated (flipped).
p2_likelihood_time   Given the current elapsed % of the candle, what fraction
                     of historical sessions would already have P2 formed?
p2_likelihood_dist   Given the current P2 distance from open, what fraction
                     of historical sessions moved further than this?
warnings             Two independent warnings:
                       · Late P1 — significant % of P1s still form after
                         the current point in the candle.
                       · Small wick — most historical P1s had a larger wick
                         than the current one.
confidence_targets   For long (if low holds) or short (if high holds):
                     the price level that X% of historical sessions reached
                     or exceeded, at confidence levels 90/80/70/60/50 %.
data_quality         Data point count + reliability flag (< 30 → unreliable).
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.p1p2_stats import P1P2Stats


# ── Result types ───────────────────────────────────────────────────────────────

class FlipRiskResult(TypedDict):
    total: int
    flipped: int
    pct: float           # percentage of sessions that flipped
    label: str           # "low" | "moderate" | "high"


class P2LikelihoodTimeResult(TypedDict):
    pct_formed_by_now: float   # % of sessions that would have P2 by current_time_pct
    p2_median_time_pct: float  # median time_pct when P2 forms
    p2_p90_time_pct: float     # 90th-percentile time_pct (90 % of P2s form by this point)
    message: str               # human-readable guidance


class P2LikelihoodDistResult(TypedDict):
    pct_moved_further: float   # % of sessions whose final P2 exceeded current_dist_abs
    current_dist_abs: float    # absolute current P2 distance from open (caller-supplied)
    p2_median_dist_abs: float  # median absolute P2 distance in historical sessions
    message: str


class WarningResult(TypedDict):
    time_warning: str | None   # e.g. "36.1% of P1s form after this point in the candle"
    dist_warning: str | None   # e.g. "78.6% of P1s have a larger wick than current"
    triggered: bool            # True if either warning fired


class ConfidenceTarget(TypedDict):
    confidence: int     # 90 | 80 | 70 | 60 | 50
    dist_pct: float     # % distance from open to target
    price: float        # absolute target price
    sample_size: int    # number of sessions used


class DataQuality(TypedDict):
    total: int
    reliable: bool      # True when total >= RELIABILITY_THRESHOLD
    message: str


class SummaryResult(TypedDict):
    flip_risk: FlipRiskResult
    p2_likelihood_time: P2LikelihoodTimeResult
    p2_likelihood_dist: P2LikelihoodDistResult
    warnings: WarningResult
    data_quality: DataQuality


# ── Constants ──────────────────────────────────────────────────────────────────

RELIABILITY_THRESHOLD = 30        # minimum sessions for reliable stats
CONFIDENCE_LEVELS = [90, 80, 70, 60, 50]

# Flip risk label boundaries (%)
_FLIP_MODERATE = 30.0
_FLIP_HIGH = 50.0

# Warning trigger thresholds (%)
_LATE_P1_TRIGGER = 30.0           # warn if >30% of P1s still form after current point
_SMALL_WICK_TRIGGER = 50.0        # warn if >50% of historical P1s have a larger wick


# ── DB layer ───────────────────────────────────────────────────────────────────

async def fetch_sessions(
    db: AsyncSession,
    symbol: str,
    timeframe: str,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    weekdays: list[int] | None = None,  # 0 = Monday … 6 = Sunday
) -> list[P1P2Stats]:
    """
    Fetch completed, valid P1P2Stats rows.

    Only returns rows where p1_side IS NOT NULL (i.e. sub-candle data was
    available and P1/P2 detection succeeded).  Rows without sub-candle data
    are OHLC-only stubs and carry no P1/P2 information.

    Weekday filter is applied in Python (cheap for typical dataset sizes).
    """
    conditions = [
        P1P2Stats.symbol == symbol,
        P1P2Stats.timeframe == timeframe,
        P1P2Stats.p1_side.is_not(None),
    ]
    if from_date:
        conditions.append(P1P2Stats.candle_open_time >= from_date)
    if to_date:
        conditions.append(P1P2Stats.candle_open_time <= to_date)

    stmt = (
        select(P1P2Stats)
        .where(and_(*conditions))
        .order_by(P1P2Stats.candle_open_time)
    )
    result = await db.execute(stmt)
    rows: list[P1P2Stats] = list(result.scalars().all())

    if weekdays is not None:
        rows = [r for r in rows if r.candle_open_time.weekday() in weekdays]

    return rows


# ── Stats layer (pure functions — no I/O) ──────────────────────────────────────

def compute_flip_risk(rows: list[P1P2Stats]) -> FlipRiskResult:
    """
    What fraction of historical sessions had P1 invalidated?

    Label thresholds:
      < 30 %  → "low"
      30–50 % → "moderate"
      ≥ 50 %  → "high"
    """
    total = len(rows)
    if total == 0:
        return {"total": 0, "flipped": 0, "pct": 0.0, "label": "low"}

    flipped = sum(1 for r in rows if r.p1_flip_occurred)
    pct = round(flipped / total * 100, 1)

    if pct < _FLIP_MODERATE:
        label = "low"
    elif pct < _FLIP_HIGH:
        label = "moderate"
    else:
        label = "high"

    return {"total": total, "flipped": flipped, "pct": pct, "label": label}


def compute_p2_likelihood_time(
    rows: list[P1P2Stats],
    current_time_pct: float,
) -> P2LikelihoodTimeResult:
    """
    Given how far we are through the current candle (0–100 %), what % of
    historical sessions would already have P2 formed by this point?

    A high pct_formed_by_now means P2 is likely in.
    A low pct_formed_by_now means P2 is unlikely to have formed yet.
    """
    times = [float(r.p2_time_pct) for r in rows if r.p2_time_pct is not None]

    if not times:
        return {
            "pct_formed_by_now": 0.0,
            "p2_median_time_pct": 0.0,
            "p2_p90_time_pct": 0.0,
            "message": "Insufficient data",
        }

    n = len(times)
    pct_by_now = round(sum(1 for t in times if t <= current_time_pct) / n * 100, 1)

    sorted_times = sorted(times)
    median = round(sorted_times[n // 2], 1)
    p90 = round(sorted_times[min(int(0.90 * n), n - 1)], 1)

    if pct_by_now >= 90:
        message = f"{pct_by_now}% of sessions would have P2 in by now"
    elif pct_by_now >= 50:
        message = f"Unclear — {pct_by_now}% of sessions would have P2 in by now"
    else:
        message = (
            f"Unlikely that P2 is in — only {pct_by_now}% of sessions "
            f"form P2 this early"
        )

    return {
        "pct_formed_by_now": pct_by_now,
        "p2_median_time_pct": median,
        "p2_p90_time_pct": p90,
        "message": message,
    }


def compute_p2_likelihood_dist(
    rows: list[P1P2Stats],
    current_dist_abs: float,
) -> P2LikelihoodDistResult:
    """
    Given the current absolute P2 distance from open, what % of historical
    sessions had their final P2 move *further* than this?

    A high pct_moved_further means the current P2 is still well within the
    expected range — most sessions went further from here.
    e.g. "98.2% of weeks moved further than 5.7%"
    """
    dists = [abs(float(r.p2_dist_pct)) for r in rows if r.p2_dist_pct is not None]

    if not dists:
        return {
            "pct_moved_further": 0.0,
            "current_dist_abs": current_dist_abs,
            "p2_median_dist_abs": 0.0,
            "message": "Insufficient data",
        }

    n = len(dists)
    pct_further = round(sum(1 for d in dists if d > current_dist_abs) / n * 100, 1)
    median_dist = round(sorted(dists)[n // 2], 2)

    if pct_further >= 90:
        message = (
            f"{pct_further}% of sessions moved further than "
            f"{current_dist_abs:.1f}% — P2 likely still developing"
        )
    elif pct_further >= 50:
        message = (
            f"{pct_further}% of sessions moved further than "
            f"{current_dist_abs:.1f}%"
        )
    else:
        message = (
            f"Only {pct_further}% of sessions moved further than "
            f"{current_dist_abs:.1f}% — P2 range may be exhausted"
        )

    return {
        "pct_moved_further": pct_further,
        "current_dist_abs": round(current_dist_abs, 2),
        "p2_median_dist_abs": median_dist,
        "message": message,
    }


def compute_warnings(
    rows: list[P1P2Stats],
    current_p1_time_pct: float,
    current_p1_dist_abs: float,
) -> WarningResult:
    """
    Two independent warnings shown in Summary View Row 3.

    Time warning  — fires when >30% of historical P1s form *after* the
                    current candle time position.  Signals that assuming
                    "P1 is in" may be premature.

    Dist warning  — fires when >50% of historical P1s had a *larger* wick
                    than the current P1.  Signals the current P1 may extend
                    further before reversing.
    """
    # ── Time warning ──────────────────────────────────────────────────────────
    p1_times = [float(r.p1_time_pct) for r in rows if r.p1_time_pct is not None]
    time_warning: str | None = None

    if p1_times:
        n = len(p1_times)
        pct_after = round(
            sum(1 for t in p1_times if t > current_p1_time_pct) / n * 100, 1
        )
        if pct_after >= _LATE_P1_TRIGGER:
            time_warning = (
                f"{pct_after}% of P1s form after this point in the candle"
            )

    # ── Distance (wick size) warning ──────────────────────────────────────────
    p1_dists = [abs(float(r.p1_dist_pct)) for r in rows if r.p1_dist_pct is not None]
    dist_warning: str | None = None

    if p1_dists:
        n = len(p1_dists)
        pct_bigger = round(
            sum(1 for d in p1_dists if d > current_p1_dist_abs) / n * 100, 1
        )
        if pct_bigger >= _SMALL_WICK_TRIGGER:
            dist_warning = (
                f"{pct_bigger}% of P1s have a larger wick than current"
            )

    return {
        "time_warning": time_warning,
        "dist_warning": dist_warning,
        "triggered": time_warning is not None or dist_warning is not None,
    }


def compute_confidence_targets(
    rows: list[P1P2Stats],
    direction: str,        # "long" | "short"
    open_price: float,
) -> list[ConfidenceTarget]:
    """
    Confidence target prices for a given trade direction.

    Long  (direction="long"):
      Filter sessions where low_held=True.  Measure how far P2 (the high)
      moved above open.  For X% confidence: the distance that X% of sessions
      reached OR exceeded.  Apply to open price → target above open.

    Short (direction="short"):
      Filter sessions where high_held=True.  Measure how far P2 (the low)
      dropped below open.  Same percentile logic → target below open.

    Confidence percentile formula:
      idx = floor((1 − confidence/100) × n)
      The value at distances[idx] is exceeded by (confidence)% of sessions.

    Returns an empty list when fewer than 2 qualifying sessions exist.
    """
    if direction == "long":
        filtered = [
            r for r in rows
            if r.low_held and r.p2_dist_pct is not None
        ]
        # p2_dist_pct is positive for long sessions (P2=high > open)
        distances = sorted(float(r.p2_dist_pct) for r in filtered)
    else:
        filtered = [
            r for r in rows
            if r.high_held and r.p2_dist_pct is not None
        ]
        # p2_dist_pct is negative for short sessions (P2=low < open); use abs
        distances = sorted(abs(float(r.p2_dist_pct)) for r in filtered)

    n = len(distances)
    if n < 2:
        return []

    targets: list[ConfidenceTarget] = []
    for confidence in CONFIDENCE_LEVELS:
        # Use integer arithmetic to avoid floating-point truncation errors.
        # e.g. int((1 - 90/100) * 10) → int(0.9999...) = 0 (wrong).
        # (100 - 90) * 10 // 100 = 1 (correct).
        idx = (100 - confidence) * n // 100
        idx = max(0, min(idx, n - 1))
        dist = round(distances[idx], 2)

        if direction == "long":
            price = round(open_price * (1 + dist / 100), 2)
        else:
            price = round(open_price * (1 - dist / 100), 2)

        targets.append({
            "confidence": confidence,
            "dist_pct": dist,
            "price": price,
            "sample_size": n,
        })

    return targets


def compute_data_quality(rows: list[P1P2Stats]) -> DataQuality:
    """Flag whether the dataset is large enough for reliable statistics."""
    total = len(rows)
    reliable = total >= RELIABILITY_THRESHOLD
    if reliable:
        msg = f"✅ {total} data points used — statistics are reliable"
    else:
        msg = (
            f"⚠️ Only {total} data points — statistics may be unreliable "
            f"(need ≥ {RELIABILITY_THRESHOLD})"
        )
    return {"total": total, "reliable": reliable, "message": msg}


# ── High-level aggregator ──────────────────────────────────────────────────────

def build_summary(
    rows: list[P1P2Stats],
    current_time_pct: float,
    current_p1_dist_abs: float,
    current_p2_dist_abs: float,
) -> SummaryResult:
    """
    Combine all stat functions into the single payload used by
    GET /api/p1p2/summary.

    Parameters
    ----------
    rows                : Valid P1P2Stats rows (from fetch_sessions).
    current_time_pct    : How far through the current candle we are (0–100).
    current_p1_dist_abs : Absolute % distance of current P1 from open.
    current_p2_dist_abs : Absolute % distance of current P2 from open.
    """
    return {
        "flip_risk": compute_flip_risk(rows),
        "p2_likelihood_time": compute_p2_likelihood_time(rows, current_time_pct),
        "p2_likelihood_dist": compute_p2_likelihood_dist(rows, current_p2_dist_abs),
        "warnings": compute_warnings(rows, current_time_pct, current_p1_dist_abs),
        "data_quality": compute_data_quality(rows),
    }
