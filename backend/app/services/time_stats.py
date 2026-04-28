"""
Time feature — computation and aggregation.

For each closed session, finds what % of the session had elapsed when the
session high and low were set, using sub-timeframe candles (1h for 1d sessions,
1d for 1w sessions).  Aggregates into 10 equal buckets and computes
reversal / continuation rates.
"""

from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ohlcv import OHLCV, SessionStats
from app.services.cache import cache_get, cache_set, stats_cache_key

BUCKET_COUNT = 10

# Sub-timeframe used to determine intra-session timing
_SUB_TF: dict[str, str] = {"1d": "1h", "1w": "1d"}

# Expected number of sub-candles per session
_CANDLES_PER_SESSION: dict[str, int] = {"1d": 24, "1w": 7}


def _bucket_index(pct: float) -> int:
    return min(int(pct / 10), BUCKET_COUNT - 1)


def _bucket_label(i: int) -> str:
    return f"{i * 10}–{(i + 1) * 10}%"


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), int(k) + 1
    if hi >= len(s):
        return s[-1]
    return s[lo] + (k - lo) * (s[hi] - s[lo])


async def compute_session_stats(
    db: AsyncSession, symbol: str, timeframe: str
) -> int:
    """
    Compute high_time_pct / low_time_pct / high_taken_out / low_taken_out for
    all closed sessions. Upserts into session_stats. Returns rows processed.
    """
    sub_tf = _SUB_TF.get(timeframe)
    if sub_tf is None:
        return 0

    # All primary-TF candles ordered oldest → newest
    sessions_q = await db.execute(
        select(OHLCV)
        .where(OHLCV.symbol == symbol, OHLCV.timeframe == timeframe)
        .order_by(OHLCV.open_time)
    )
    sessions: list[OHLCV] = list(sessions_q.scalars())

    if len(sessions) < 2:
        return 0

    # All sub-TF candles for this symbol (loaded once)
    sub_q = await db.execute(
        select(OHLCV)
        .where(OHLCV.symbol == symbol, OHLCV.timeframe == sub_tf)
        .order_by(OHLCV.open_time)
    )
    sub_candles: list[OHLCV] = list(sub_q.scalars())

    processed = 0

    # Iterate closed sessions only (skip last — may be open)
    for i, session in enumerate(sessions[:-1]):
        next_session = sessions[i + 1]
        session_start = session.open_time
        session_end = next_session.open_time

        intra = [
            c for c in sub_candles
            if session_start <= c.open_time < session_end
        ]
        if not intra:
            continue

        n = len(intra)
        high_idx = max(range(n), key=lambda j: float(intra[j].high))
        low_idx = min(range(n), key=lambda j: float(intra[j].low))

        # Midpoint of the sub-candle as fraction of session
        high_time_pct = (high_idx + 0.5) / n * 100
        low_time_pct = (low_idx + 0.5) / n * 100

        high_taken_out = float(next_session.high) > float(session.high)
        low_taken_out = float(next_session.low) < float(session.low)

        await db.execute(
            text("""
                INSERT INTO session_stats
                    (symbol, timeframe, session_date,
                     high_time_pct, low_time_pct,
                     high_taken_out, low_taken_out)
                VALUES
                    (:symbol, :timeframe, :session_date,
                     :high_time_pct, :low_time_pct,
                     :high_taken_out, :low_taken_out)
                ON CONFLICT (symbol, timeframe, session_date)
                DO UPDATE SET
                    high_time_pct  = EXCLUDED.high_time_pct,
                    low_time_pct   = EXCLUDED.low_time_pct,
                    high_taken_out = EXCLUDED.high_taken_out,
                    low_taken_out  = EXCLUDED.low_taken_out
            """),
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "session_date": session_start,
                "high_time_pct": round(high_time_pct, 2),
                "low_time_pct": round(low_time_pct, 2),
                "high_taken_out": high_taken_out,
                "low_taken_out": low_taken_out,
            },
        )
        processed += 1

    await db.commit()
    return processed


async def get_time_distribution(
    db: AsyncSession, symbol: str, timeframe: str
) -> dict:
    """
    Aggregate session_stats into reversal / continuation rates by time bucket.
    Returns distribution + current session position. Redis-cached 15 min.
    """
    cache_key = stats_cache_key(symbol, timeframe, "time")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Fetch rows with known outcomes only
    rows_q = await db.execute(
        select(SessionStats)
        .where(
            SessionStats.symbol == symbol,
            SessionStats.timeframe == timeframe,
            SessionStats.high_time_pct.isnot(None),
            SessionStats.high_taken_out.isnot(None),
        )
        .order_by(SessionStats.session_date)
    )
    rows: list[SessionStats] = list(rows_q.scalars())

    high_buckets = [
        {"bucket": _bucket_label(i), "bucket_index": i, "count": 0, "reversal_count": 0}
        for i in range(BUCKET_COUNT)
    ]
    low_buckets = [
        {"bucket": _bucket_label(i), "bucket_index": i, "count": 0, "reversal_count": 0}
        for i in range(BUCKET_COUNT)
    ]

    for row in rows:
        hb = _bucket_index(float(row.high_time_pct))
        high_buckets[hb]["count"] += 1
        if not row.high_taken_out:
            high_buckets[hb]["reversal_count"] += 1

        lb = _bucket_index(float(row.low_time_pct))
        low_buckets[lb]["count"] += 1
        if not row.low_taken_out:
            low_buckets[lb]["reversal_count"] += 1

    for b in high_buckets:
        n = b["count"]
        b["reversal_rate"] = round(b["reversal_count"] / n, 4) if n > 0 else None
        b["continuation_rate"] = round(1 - b["reversal_rate"], 4) if b["reversal_rate"] is not None else None

    for b in low_buckets:
        n = b["count"]
        b["reversal_rate"] = round(b["reversal_count"] / n, 4) if n > 0 else None
        b["continuation_rate"] = round(1 - b["reversal_rate"], 4) if b["reversal_rate"] is not None else None

    current_session = await _get_current_session(db, symbol, timeframe, rows)

    payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "total_sessions": len(rows),
        "high_distribution": high_buckets,
        "low_distribution": low_buckets,
        "current_session": current_session,
    }

    await cache_set(cache_key, payload)
    return payload


async def _get_current_session(
    db: AsyncSession,
    symbol: str,
    timeframe: str,
    historical_rows: list[SessionStats],
) -> dict | None:
    """Compute current session's high/low position using sub-TF candles."""
    sub_tf = _SUB_TF.get(timeframe)
    expected_candles = _CANDLES_PER_SESSION.get(timeframe)
    if sub_tf is None or expected_candles is None:
        return None

    # Most recent primary candle = current (possibly open) session
    session_q = await db.execute(
        select(OHLCV)
        .where(OHLCV.symbol == symbol, OHLCV.timeframe == timeframe)
        .order_by(OHLCV.open_time.desc())
        .limit(1)
    )
    session = session_q.scalar_one_or_none()
    if session is None:
        return None

    session_start = session.open_time
    # Use next-candle boundary as approximate session end
    if timeframe == "1d":
        session_end = session_start + timedelta(hours=24)
    else:
        session_end = session_start + timedelta(weeks=1)

    intra_q = await db.execute(
        select(OHLCV)
        .where(
            OHLCV.symbol == symbol,
            OHLCV.timeframe == sub_tf,
            OHLCV.open_time >= session_start,
            OHLCV.open_time < session_end,
        )
        .order_by(OHLCV.open_time)
    )
    intra: list[OHLCV] = list(intra_q.scalars())

    if not intra:
        return None

    elapsed = len(intra)
    high_idx = max(range(elapsed), key=lambda j: float(intra[j].high))
    low_idx = min(range(elapsed), key=lambda j: float(intra[j].low))

    # Normalize against full expected session length so current is comparable to history
    high_time_pct = (high_idx + 0.5) / expected_candles * 100
    low_time_pct = (low_idx + 0.5) / expected_candles * 100

    high_bucket = _bucket_index(high_time_pct)
    low_bucket = _bucket_index(low_time_pct)

    # 20th-percentile threshold for "early" flag
    hist_high = [float(r.high_time_pct) for r in historical_rows if r.high_time_pct is not None]
    hist_low = [float(r.low_time_pct) for r in historical_rows if r.low_time_pct is not None]
    early_threshold_high = _percentile(hist_high, 20) if hist_high else 20.0
    early_threshold_low = _percentile(hist_low, 20) if hist_low else 20.0

    return {
        "high_time_pct": round(high_time_pct, 2),
        "low_time_pct": round(low_time_pct, 2),
        "high_bucket": high_bucket,
        "low_bucket": low_bucket,
        "early_high": bool(high_time_pct <= early_threshold_high),
        "early_low": bool(low_time_pct <= early_threshold_low),
        "elapsed_pct": round(elapsed / expected_candles * 100, 1),
        "session_start": session_start.isoformat(),
    }
