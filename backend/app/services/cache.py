import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def cache_get(key: str) -> Any | None:
    r = get_redis()
    value = await r.get(key)
    return json.loads(value) if value else None


async def cache_set(key: str, value: Any, ttl: int = settings.stats_cache_ttl) -> None:
    r = get_redis()
    await r.set(key, json.dumps(value), ex=ttl)


async def cache_delete(key: str) -> None:
    r = get_redis()
    await r.delete(key)


def stats_cache_key(symbol: str, timeframe: str, stat_type: str) -> str:
    return f"stats:{symbol}:{timeframe}:{stat_type}"
