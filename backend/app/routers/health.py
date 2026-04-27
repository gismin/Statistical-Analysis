from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.cache import get_redis

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/health/detailed")
async def health_detailed(db: AsyncSession = Depends(get_db)):
    results: dict = {"status": "ok", "checks": {}}

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        results["checks"]["database"] = "ok"
    except Exception as e:
        results["checks"]["database"] = f"error: {e}"
        results["status"] = "degraded"

    # Redis check
    try:
        r = get_redis()
        await r.ping()
        results["checks"]["redis"] = "ok"
    except Exception as e:
        results["checks"]["redis"] = f"error: {e}"
        results["status"] = "degraded"

    return results
