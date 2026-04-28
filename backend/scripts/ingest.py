"""
OHLCV ingestion + session stats computation.

Usage:
    python -m scripts.ingest                       # all symbols + timeframes
    python -m scripts.ingest --symbol BTC/USDT     # single symbol
    python -m scripts.ingest --tf 1d               # single primary timeframe
    python -m scripts.ingest --skip-stats          # skip session stat computation
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import aiohttp
import ccxt.async_support as ccxt
from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv()

from app.database import AsyncSessionLocal, engine, init_db  # noqa: E402
from app.models.ohlcv import OHLCV  # noqa: E402
from app.services.time_stats import compute_session_stats  # noqa: E402

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

# Primary stat timeframes — these drive the Time / Distance features
PRIMARY_TIMEFRAMES = ["1d", "1w"]

# Helper timeframe ingested to compute intra-session timing
HELPER_TIMEFRAMES = ["1h"]

# How many candles to fetch for primary timeframes (single request)
PRIMARY_BACKFILL_LIMIT = 500

# How far back to fetch 1h data (in days) — matches ~500 daily sessions
HOURLY_BACKFILL_DAYS = 500


async def fetch_ohlcv(exchange: ccxt.Exchange, symbol: str, timeframe: str) -> list[dict]:
    """Fetch up to PRIMARY_BACKFILL_LIMIT candles (single request)."""
    logger.info(f"Fetching {symbol} {timeframe} ...")
    raw = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=PRIMARY_BACKFILL_LIMIT)
    return _rows_to_dicts(symbol, timeframe, raw)


async def fetch_ohlcv_paginated(
    exchange: ccxt.Exchange, symbol: str, timeframe: str, since_ms: int
) -> list[dict]:
    """Paginate through all candles from since_ms to now (1000 per request)."""
    logger.info(f"Fetching {symbol} {timeframe} (paginated from {since_ms}) ...")
    all_rows: list = []
    while True:
        batch = await exchange.fetch_ohlcv(
            symbol, timeframe=timeframe, since=since_ms, limit=1000
        )
        if not batch:
            break
        all_rows.extend(batch)
        if len(batch) < 1000:
            break
        since_ms = batch[-1][0] + 1  # advance past last candle
    logger.info(f"  {symbol} {timeframe}: fetched {len(all_rows)} candles total")
    return _rows_to_dicts(symbol, timeframe, all_rows)


def _rows_to_dicts(symbol: str, timeframe: str, raw: list) -> list[dict]:
    return [
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "open_time": datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        }
        for row in raw
    ]


UPSERT_BATCH_SIZE = 1000  # asyncpg limit: 32767 params; 1000 rows × 8 cols = 8000


async def upsert_candles(candles: list[dict]) -> int:
    if not candles:
        return 0
    total = 0
    # Split into batches to stay under asyncpg's 32767 parameter limit
    for i in range(0, len(candles), UPSERT_BATCH_SIZE):
        batch = candles[i : i + UPSERT_BATCH_SIZE]
        async with AsyncSessionLocal() as session:
            stmt = pg_insert(OHLCV).values(batch)
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
        total += len(batch)
    return total


async def run(
    symbols: list[str],
    primary_timeframes: list[str],
    skip_stats: bool,
) -> None:
    await init_db()

    # ThreadedResolver uses OS DNS — aiodns fails on Windows/WSL2
    resolver = aiohttp.ThreadedResolver()
    connector = aiohttp.TCPConnector(resolver=resolver)
    session = aiohttp.ClientSession(connector=connector)
    exchange = ccxt.binance({"enableRateLimit": True, "session": session})

    try:
        total = 0

        # ── Primary timeframes (1d, 1w) ──────────────────────────────────────
        for symbol in symbols:
            for tf in primary_timeframes:
                try:
                    candles = await fetch_ohlcv(exchange, symbol, tf)
                    n = await upsert_candles(candles)
                    total += n
                    logger.info(f"  {symbol} {tf}: upserted {n} candles")
                except Exception as e:
                    logger.error(f"  {symbol} {tf}: failed — {e}")

        # ── Hourly helper data (needed for 1d session timing) ─────────────────
        since_1h = int(
            (datetime.now(timezone.utc) - timedelta(days=HOURLY_BACKFILL_DAYS)).timestamp() * 1000
        )
        for symbol in symbols:
            try:
                candles = await fetch_ohlcv_paginated(exchange, symbol, "1h", since_1h)
                n = await upsert_candles(candles)
                total += n
                logger.info(f"  {symbol} 1h: upserted {n} candles")
            except Exception as e:
                logger.error(f"  {symbol} 1h: failed — {e}")

        logger.info(f"Ingestion complete. Total candles upserted: {total}")

        # ── Session stats computation ─────────────────────────────────────────
        if not skip_stats:
            logger.info("Computing session stats ...")
            async with AsyncSessionLocal() as db:
                for symbol in symbols:
                    for tf in primary_timeframes:
                        try:
                            processed = await compute_session_stats(db, symbol, tf)
                            logger.info(f"  {symbol} {tf}: {processed} time sessions computed")
                        except Exception as e:
                            logger.error(f"  {symbol} {tf}: time stats failed — {e}")

            logger.info("Session stats done.")

    finally:
        await exchange.close()
        await session.close()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest OHLCV data and compute session stats")
    parser.add_argument("--symbol", help="Single symbol, e.g. BTC/USDT")
    parser.add_argument("--tf", help="Single primary timeframe, e.g. 1d")
    parser.add_argument("--skip-stats", action="store_true", help="Skip session stat computation")
    args = parser.parse_args()

    symbols = [args.symbol] if args.symbol else SYMBOLS
    timeframes = [args.tf] if args.tf else PRIMARY_TIMEFRAMES

    asyncio.run(run(symbols, timeframes, skip_stats=args.skip_stats))
