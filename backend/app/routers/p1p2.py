"""
P1/P2 API router.

Endpoints
---------
GET  /api/p1p2/summary
     Returns the full Summary View payload: flip risk, P2 likelihood (time +
     distance), warnings, and data quality.

GET  /api/p1p2/confidence-targets
     Returns long and short confidence target prices at 90/80/70/60/50 %.

GET  /api/p1p2/symbols
     Lists available symbols for the P1/P2 feature.

All endpoints accept the following common query parameters:
  symbol           e.g. "BTC/USDT"
  timeframe        one of: 1h | 4h | 1d | 1w | 1mo
  from_date        ISO-8601 date string, e.g. "2022-09-19"  (optional)
  to_date          ISO-8601 date string, e.g. "2025-09-18"  (optional)
  weekdays         comma-separated weekday numbers 0=Mon…6=Sun (optional)
                   e.g. "0,1,2,3,4" for Mon–Fri only
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.p1p2_stats import (
    build_summary,
    compute_confidence_targets,
    compute_data_quality,
    fetch_sessions,
)

router = APIRouter(prefix="/api/p1p2", tags=["p1p2"])

# ── Validation constants ───────────────────────────────────────────────────────

_VALID_TIMEFRAMES = {"1h", "4h", "1d", "1w", "1mo"}

_VALID_SYMBOLS = {
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
}


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _validate(symbol: str, timeframe: str) -> None:
    if symbol not in _VALID_SYMBOLS:
        raise HTTPException(400, f"Unknown symbol: {symbol!r}. "
                                 f"Valid: {sorted(_VALID_SYMBOLS)}")
    if timeframe not in _VALID_TIMEFRAMES:
        raise HTTPException(400, f"Unknown timeframe: {timeframe!r}. "
                                 f"Valid: {sorted(_VALID_TIMEFRAMES)}")


def _parse_date(value: str | None, param: str) -> datetime | None:
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(
            400, f"Invalid {param}: {value!r} — expected ISO-8601 date, e.g. '2022-09-19'"
        )


def _parse_weekdays(value: str | None) -> list[int] | None:
    if value is None:
        return None
    try:
        days = [int(d.strip()) for d in value.split(",") if d.strip()]
        if not all(0 <= d <= 6 for d in days):
            raise ValueError
        return days
    except ValueError:
        raise HTTPException(
            400, "weekdays must be comma-separated integers 0–6 (0=Mon, 6=Sun)"
        )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/summary")
async def summary(
    symbol: str = Query(..., example="BTC/USDT"),
    timeframe: str = Query(..., example="1w"),
    current_time_pct: float = Query(
        ...,
        ge=0.0, le=100.0,
        description="How far through the current candle we are (0–100 %)",
        example=35.0,
    ),
    current_p1_dist_abs: float = Query(
        ...,
        ge=0.0,
        description="Absolute % distance of current P1 from open",
        example=2.5,
    ),
    current_p2_dist_abs: float = Query(
        ...,
        ge=0.0,
        description="Absolute % distance of current P2 from open",
        example=4.1,
    ),
    from_date: str | None = Query(None, example="2022-09-19"),
    to_date: str | None = Query(None, example="2025-09-18"),
    weekdays: str | None = Query(None, example="0,1,2,3,4"),
    db: AsyncSession = Depends(get_db),
):
    """
    Full Summary View payload.

    Combines flip risk, P2 likelihood (time + distance), warnings, and
    data quality into a single response object.
    """
    _validate(symbol, timeframe)
    rows = await fetch_sessions(
        db, symbol, timeframe,
        from_date=_parse_date(from_date, "from_date"),
        to_date=_parse_date(to_date, "to_date"),
        weekdays=_parse_weekdays(weekdays),
    )

    if not rows:
        raise HTTPException(
            404,
            "No P1/P2 data found for this symbol/timeframe. "
            "Run the ingest + compute pipeline first.",
        )

    return build_summary(
        rows,
        current_time_pct=current_time_pct,
        current_p1_dist_abs=current_p1_dist_abs,
        current_p2_dist_abs=current_p2_dist_abs,
    )


@router.get("/confidence-targets")
async def confidence_targets(
    symbol: str = Query(..., example="BTC/USDT"),
    timeframe: str = Query(..., example="1w"),
    open_price: float = Query(
        ...,
        gt=0.0,
        description="Current candle open price",
        example=65000.0,
    ),
    from_date: str | None = Query(None, example="2022-09-19"),
    to_date: str | None = Query(None, example="2025-09-18"),
    weekdays: str | None = Query(None, example="0,1,2,3,4"),
    db: AsyncSession = Depends(get_db),
):
    """
    Confidence target prices for both long and short scenarios.

    Returns:
      long_targets  — price levels that X% of weeks where the low held
                      would have reached above open.
      short_targets — price levels that X% of weeks where the high held
                      would have reached below open.
      data_quality  — sample size + reliability flag.
    """
    _validate(symbol, timeframe)
    rows = await fetch_sessions(
        db, symbol, timeframe,
        from_date=_parse_date(from_date, "from_date"),
        to_date=_parse_date(to_date, "to_date"),
        weekdays=_parse_weekdays(weekdays),
    )

    if not rows:
        raise HTTPException(
            404,
            "No P1/P2 data found for this symbol/timeframe. "
            "Run the ingest + compute pipeline first.",
        )

    long_targets = compute_confidence_targets(rows, "long", open_price)
    short_targets = compute_confidence_targets(rows, "short", open_price)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "open_price": open_price,
        "long_targets": long_targets,
        "short_targets": short_targets,
        "data_quality": compute_data_quality(rows),
    }


@router.get("/symbols")
async def list_symbols():
    """List all symbols supported by the P1/P2 feature."""
    return {"symbols": sorted(_VALID_SYMBOLS)}
