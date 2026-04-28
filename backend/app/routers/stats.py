from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.distance_stats import compute_distance_stats, get_distance_distribution
from app.services.time_stats import compute_session_stats, get_time_distribution

router = APIRouter(prefix="/api/stats", tags=["stats"])

_VALID_TIMEFRAMES = {"1d", "1w"}
_VALID_SYMBOLS = {
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
}


def _validate(symbol: str, timeframe: str) -> None:
    if symbol not in _VALID_SYMBOLS:
        raise HTTPException(400, f"Unknown symbol: {symbol}")
    if timeframe not in _VALID_TIMEFRAMES:
        raise HTTPException(400, f"timeframe must be one of {sorted(_VALID_TIMEFRAMES)}")


@router.get("/time")
async def time_stats(
    symbol: str = Query(..., example="BTC/USDT"),
    timeframe: str = Query(..., example="1d"),
    db: AsyncSession = Depends(get_db),
):
    """Return time-distribution stats for a given symbol and timeframe."""
    _validate(symbol, timeframe)
    result = await get_time_distribution(db, symbol, timeframe)
    if result["total_sessions"] == 0:
        raise HTTPException(
            404,
            "No computed stats found. Run the ingest + compute pipeline first.",
        )
    return result


@router.post("/time/compute")
async def compute_time_stats(
    symbol: str = Query(..., example="BTC/USDT"),
    timeframe: str = Query(..., example="1d"),
    db: AsyncSession = Depends(get_db),
):
    """Trigger on-demand recomputation of session stats for a symbol/timeframe."""
    _validate(symbol, timeframe)
    processed = await compute_session_stats(db, symbol, timeframe)
    return {"symbol": symbol, "timeframe": timeframe, "sessions_processed": processed}


@router.get("/distance")
async def distance_stats(
    symbol: str = Query(..., example="BTC/USDT"),
    timeframe: str = Query(..., example="1d"),
    db: AsyncSession = Depends(get_db),
):
    """Return range-vs-ATR distribution stats for a given symbol and timeframe."""
    _validate(symbol, timeframe)
    result = await get_distance_distribution(db, symbol, timeframe)
    if result["total_sessions"] == 0:
        raise HTTPException(
            404,
            "No distance stats found. Run the ingest + compute pipeline first.",
        )
    return result


@router.post("/distance/compute")
async def compute_distance_stats_endpoint(
    symbol: str = Query(..., example="BTC/USDT"),
    timeframe: str = Query(..., example="1d"),
    db: AsyncSession = Depends(get_db),
):
    """Trigger on-demand recomputation of distance stats for a symbol/timeframe."""
    _validate(symbol, timeframe)
    processed = await compute_distance_stats(db, symbol, timeframe)
    return {"symbol": symbol, "timeframe": timeframe, "sessions_processed": processed}


@router.get("/symbols")
async def list_symbols():
    """Return the list of tracked symbols."""
    return {"symbols": sorted(_VALID_SYMBOLS)}
