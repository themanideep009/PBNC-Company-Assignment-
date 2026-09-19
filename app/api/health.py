"""
Health check endpoint — verifies DB and Redis connectivity.
Unprotected (no JWT required) per spec.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis import get_redis

router = APIRouter(tags=["Health"])


@router.get("/healthz", summary="Health check")
def healthz(db: Session = Depends(get_db)):
    """
    Health check endpoint — verifies database and Redis connectivity.
    Returns 200 with component status if healthy.
    """
    health = {"status": "healthy", "components": {}}

    # Check PostgreSQL
    try:
        db.execute(text("SELECT 1"))
        health["components"]["postgres"] = "connected"
    except Exception as e:
        health["status"] = "degraded"
        health["components"]["postgres"] = f"error: {str(e)}"

    # Check Redis
    try:
        redis = get_redis()
        redis.ping()
        health["components"]["redis"] = "connected"
    except Exception as e:
        health["status"] = "degraded"
        health["components"]["redis"] = f"error: {str(e)}"

    return health
