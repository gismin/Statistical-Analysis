"""
OHLCV ingestion script — fetches historical candles from Binance via CCXT
and upserts them into the database.

Usage:
    python -m scripts.ingest                     # ingest all symbols + timeframes
    python -m scripts.ingest --symbol BTC/USDT   # single symbol
    python -m scripts.ingest --tf 1d             # single timeframe
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

import ccxt.async_support as ccxt
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv()

from app.database import AsyncSessionLocal, engine, init_db  # noqa: E402
from app.models.ohlcv import OHLCV  # noqa: E402

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "DOGE/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "DOT/USDT",
]

TIMEFRAMES = ["1d", "1w"]

# How many candles to backfill per symbol/timeframe
BACKFILL_LIMIT = 500


async def fetch_ohlcv(exchange: ccxt.Exchange, symbol: str, timeframe: str) -> list[dict]:
    logger.info(f"Fetching {symbol} {timeframe} ...")
    raw = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=BACKFILL_LIMIT)
    candles = []
    for row in raw:
        ts, o, h, l, c, v = row
        candles.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "open_time": datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": float(v),
            }
        )
    return candles


async def upsert_candles(candles: list[dict]) -> int:
    if not candles:
        return 0
    async with AsyncSessionLocal() as session:
        stmt = pg_insert(OHLCV).values(candles)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ohlcv_symbol_tf_time",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        await session.execute(stmt)
        await session.commit()
    return len(candles)


async def run(symbols: list[str], timeframes: list[str]) -> None:
    await init_db()

    exchange = ccxt.binance({"enableRateLimit": True})

    try:
        total = 0
        for symbol in symbols:
            for tf in timeframes:
                try:
                    candles = await fetch_ohlcv(exchange, symbol, tf)
                    n = await upsert_candles(candles)
                    total += n
                    logger.info(f"  {symbol} {tf}: upserted {n} candles")
                except Exception as e:
                    logger.error(f"  {symbol} {tf}: failed — {e}")

        logger.info(f"Done. Total candles upserted: {total}")
    finally:
        await exchange.close()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest OHLCV data")
    parser.add_argument("--symbol", help="Single symbol to ingest, e.g. BTC/USDT")
    parser.add_argument("--tf", help="Single timeframe to ingest, e.g. 1d")
    args = parser.parse_args()

    symbols = [args.symbol] if args.symbol else SYMBOLS
    timeframes = [args.tf] if args.tf else TIMEFRAMES

    asyncio.run(run(symbols, timeframes))
