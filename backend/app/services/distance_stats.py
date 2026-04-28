"""
Distance feature — computation and aggregation.

For each closed session, computes ATR(14) from the 14 prior sessions and
normalises the session's range against it.  Aggregates into 5 buckets and
computes reversal / continuation rates.

Reversal definition: neither the session high NOR the session low was taken
out in the following session (range held). Continuation: at least one side
was extended.
"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ohlcv import OHLCV, SessionStats
from app.services.cache import cache_get, cache_set, stats_cache_key

# Bucket boundaries (range as % of ATR14): 0–25, 25–50, 50–75, 75–100, >100
BUCKET_BOUNDARIES = [25.0, 50.0, 75.0, 100.0]
BUCKET_LABELS = ["0–25%", "25–50%", "50–75%", "75–100%", ">100%"]
BUCKET_COUNT = 5


def _bucket_index(pct: float) -> int:
    for i, boundary in enumerate(BUCKET_BOUNDARIES):
        if pct < boundary:
            return i
    return BUCKET_COUNT - 1


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), int(k) + 1
    if hi >= len(s):
        return s[-1]
    return s[lo] + (k - lo) * (s[hi] - s[lo])


def _true_range(h: float, l: float, prev_close: float | None) -> float:
    if prev_close is None:
        return h - l
    return max(h - l, abs(h - prev_close), abs(l - prev_close))


async def compute_distance_stats(
    db: AsyncSession, symbol: str, timeframe: str
) -> int:
    """
    Compute atr14 and range_atr_pct for all closed sessions that have at
    least 14 prior sessions. Upserts into session_stats. Returns rows processed.
    """
    sessions_q = await db.execute(
        select(OHLCV)
        .where(OHLCV.symbol == symbol, OHLCV.timeframe == timeframe)
        .order_by(OHLCV.open_time)
    )
    sessions: list[OHLCV] = list(sessions_q.scalars())

    # Need 14 sessions for ATR window + at least 1 to process + 1 closed check
    if len(sessions) < 16:
        return 0

    processed = 0

    # Iterate closed sessions only (skip last — may still be open)
    for i in range(14, len(sessions) - 1):
        # True ranges for the 14 sessions immediately before session i
        trs: list[float] = []
        for j in range(i - 14, i):
            h = float(sessions[j].high)
            l = float(sessions[j].low)
            prev_close = float(sessions[j - 1].close) if j > 0 else None
            trs.append(_true_range(h, l, prev_close))

        atr14 = sum(trs) / 14
        if atr14 == 0:
            continue

        session = sessions[i]
        rng = float(session.high) - float(session.low)
        range_atr_pct = round(rng / atr14 * 100, 4)

        await db.execute(
            text("""
                INSERT INTO session_stats
                    (symbol, timeframe, session_date, atr14, range_atr_pct)
                VALUES
                    (:symbol, :timeframe, :session_date, :atr14, :range_atr_pct)
                ON CONFLICT (symbol, timeframe, session_date)
                DO UPDATE SET
                    atr14         = EXCLUDED.atr14,
                    range_atr_pct = EXCLUDED.range_atr_pct
            """),
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "session_date": session.open_time,
                "atr14": round(atr14, 8),
                "range_atr_pct": range_atr_pct,
            },
        )
        processed += 1

    await db.commit()
    return processed


async def get_distance_distribution(
    db: AsyncSession, symbol: str, timeframe: str
) -> dict:
    """
    Aggregate session_stats into reversal / continuation rates by range bucket.
    Returns distribution + current session position. Redis-cached 15 min.
    """
    cache_key = stats_cache_key(symbol, timeframe, "distance")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    rows_q = await db.execute(
        select(SessionStats)
        .where(
            SessionStats.symbol == symbol,
            SessionStats.timeframe == timeframe,
            SessionStats.range_atr_pct.isnot(None),
            SessionStats.high_taken_out.isnot(None),
            SessionStats.low_taken_out.isnot(None),
        )
        .order_by(SessionStats.session_date)
    )
    rows: list[SessionStats] = list(rows_q.scalars())

    buckets = [
        {
            "bucket": BUCKET_LABELS[i],
            "bucket_index": i,
            "count": 0,
            "reversal_count": 0,
        }
        for i in range(BUCKET_COUNT)
    ]

    hist_pcts: list[float] = []

    for row in rows:
        pct = float(row.range_atr_pct)
        hist_pcts.append(pct)
        b = _bucket_index(pct)
        buckets[b]["count"] += 1
        # Reversal = range held (neither side taken out)
        if not row.high_taken_out and not row.low_taken_out:
            buckets[b]["reversal_count"] += 1

    for bkt in buckets:
        n = bkt["count"]
        bkt["reversal_rate"] = round(bkt["reversal_count"] / n, 4) if n > 0 else None
        bkt["continuation_rate"] = (
            round(1 - bkt["reversal_rate"], 4) if bkt["reversal_rate"] is not None else None
        )

    small_range_threshold = _percentile(hist_pcts, 25) if hist_pcts else 25.0

    current_session = await _get_current_distance_session(
        db, symbol, timeframe, small_range_threshold
    )

    payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "total_sessions": len(rows),
        "distribution": buckets,
        "small_range_threshold": round(small_range_threshold, 2),
        "current_session": current_session,
    }

    await cache_set(cache_key, payload)
    return payload


async def _get_current_distance_session(
    db: AsyncSession,
    symbol: str,
    timeframe: str,
    small_range_threshold: float,
) -> dict | None:
    """Compute the current (possibly open) session's range_atr_pct."""
    # Need last 15 sessions: 14 for ATR + 1 current
    sessions_q = await db.execute(
        select(OHLCV)
        .where(OHLCV.symbol == symbol, OHLCV.timeframe == timeframe)
        .order_by(OHLCV.open_time.desc())
        .limit(15)
    )
    recent: list[OHLCV] = list(reversed(sessions_q.scalars().all()))

    if len(recent) < 15:
        return None

    # ATR14 from the 14 sessions before the current (last) one
    trs: list[float] = []
    for j in range(0, 14):
        h = float(recent[j].high)
        l = float(recent[j].low)
        prev_close = float(recent[j - 1].close) if j > 0 else None
        trs.append(_true_range(h, l, prev_close))

    atr14 = sum(trs) / 14
    if atr14 == 0:
        return None

    current = recent[-1]
    rng = float(current.high) - float(current.low)
    range_atr_pct = rng / atr14 * 100
    bucket = _bucket_index(range_atr_pct)

    return {
        "range_atr_pct": round(range_atr_pct, 2),
        "atr14": round(atr14, 8),
        "current_range": round(rng, 8),
        "bucket": bucket,
        "small_range": bool(range_atr_pct < small_range_threshold),
        "session_start": current.open_time.isoformat(),
    }
