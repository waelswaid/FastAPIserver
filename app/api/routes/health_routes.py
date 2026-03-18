import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    checks = {}
    status = "healthy"
    status_code = 200

    # Database check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "up"}
    except Exception as e:
        logger.error("Health check: database is down: %s", e)
        checks["database"] = {"status": "down", "detail": "unavailable"}
        status = "unhealthy"
        status_code = 503

    # Redis check
    try:
        redis = get_redis()
        if redis is None:
            raise ConnectionError("Redis client not initialized")
        await redis.ping()
        checks["redis"] = {"status": "up"}
    except Exception as e:
        logger.error("Health check: redis is down: %s", e)
        checks["redis"] = {"status": "down", "detail": "unavailable"}
        if status != "unhealthy":
            status = "degraded"

    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "checks": checks},
    )
