"""
P1/P2 statistics computation — DB layer.

Reads completed parent candles and their sub-candles from the ohlcv table,
runs detect_p1_p2() on each, and upserts results into p1p2_stats.

Sub-candle resolution mapping (parent → sub):
    "1d"  → "1h"
    "1w"  → "1h"
    "1mo" → "1d"  (not yet ingested; reserved for future use)
"""

from __future__ import annotations

from bisect import bisect_left

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ohlcv import OHLCV
from app.models.p1p2_stats import P1P2Stats
from app.services.p1p2_detect import SubCandle, detect_p1_p2

_SUB_TF: dict[str, str] = {
    "1d": "1h",
    "1w": "1h",
    "1mo": "1d",
}

_UPSERT_BATCH = 500  # 27 cols × 500 rows = 13 500 params — well under asyncpg limit


def _result_to_dict(r) -> dict:
    return {
        "p1_side": r.p1_side,
        "p1_price": r.p1_price,
        "p1_time": r.p1_time,
        "p1_dist_pct": r.p1_dist_pct,
        "p1_time_pct": r.p1_time_pct,
        "p1_flip_count": r.p1_flip_count,
        "p1_flip_occurred": r.p1_flip_occurred,
        "final_p1_price": r.final_p1_price,
        "final_p1_time": r.final_p1_time,
        "final_p1_dist_pct": r.final_p1_dist_pct,
        "final_p1_time_pct": r.final_p1_time_pct,
        "p2_price": r.p2_price,
        "p2_time": r.p2_time,
        "p2_dist_pct": r.p2_dist_pct,
        "p2_time_pct": r.p2_time_pct,
        "is_bullish": r.is_bullish,
        "low_held": r.low_held,
        "high_held": r.high_held,
        "sub_candle_count": r.sub_candle_count,
    }


async def compute_p1p2_stats(db: AsyncSession, symbol: str, timeframe: str) -> int:
    """
    Compute P1/P2 for all completed candles of symbol/timeframe and upsert
    into p1p2_stats.  Returns the number of rows upserted.
    """
    sub_tf = _SUB_TF.get(timeframe)
    if sub_tf is None:
        return 0

    # ── Load candles ──────────────────────────────────────────────────────────

    sessions_res = await db.execute(
        select(OHLCV)
        .where(OHLCV.symbol == symbol, OHLCV.timeframe == timeframe)
        .order_by(OHLCV.open_time)
    )
    sessions: list[OHLCV] = list(sessions_res.scalars())

    if len(sessions) < 2:
        return 0

    sub_res = await db.execute(
        select(OHLCV)
        .where(OHLCV.symbol == symbol, OHLCV.timeframe == sub_tf)
        .order_by(OHLCV.open_time)
    )
    sub_rows: list[OHLCV] = list(sub_res.scalars())

    # Build a sorted list of open_times for bisect lookups
    sub_times = [s.open_time for s in sub_rows]

    # ── Process each completed candle (skip the last — may still be open) ─────

    pending: list[dict] = []
    total_upserted = 0

    for i, session in enumerate(sessions[:-1]):
        next_open = sessions[i + 1].open_time

        lo = bisect_left(sub_times, session.open_time)
        hi = bisect_left(sub_times, next_open)

        sub_candles = [
            SubCandle(
                open_time=sub_rows[j].open_time,
                open=float(sub_rows[j].open),
                high=float(sub_rows[j].high),
                low=float(sub_rows[j].low),
                close=float(sub_rows[j].close),
            )
            for j in range(lo, hi)
        ]

        result = detect_p1_p2(
            open_price=float(session.open),
            high=float(session.high),
            low=float(session.low),
            close=float(session.close),
            candle_open_time=session.open_time,
            timeframe=timeframe,
            sub_candles=sub_candles,
        )

        if result is None:
            continue

        pending.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "candle_open_time": session.open_time,
                "open_price": float(session.open),
                "high": float(session.high),
                "low": float(session.low),
                "close": float(session.close),
                **_result_to_dict(result),
            }
        )

        if len(pending) >= _UPSERT_BATCH:
            total_upserted += await _upsert_batch(db, pending)
            pending.clear()

    if pending:
        total_upserted += await _upsert_batch(db, pending)

    return total_upserted


async def _upsert_batch(db: AsyncSession, rows: list[dict]) -> int:
    update_cols = {
        c: getattr(pg_insert(P1P2Stats).excluded, c)
        for c in rows[0]
        if c not in ("symbol", "timeframe", "candle_open_time")
    }
    stmt = (
        pg_insert(P1P2Stats)
        .values(rows)
        .on_conflict_do_update(
            constraint="uq_p1p2_symbol_tf_time",
            set_=update_cols,
        )
    )
    await db.execute(stmt)
    await db.commit()
    return len(rows)
