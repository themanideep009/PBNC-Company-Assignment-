"""
Redis connection management.

Used for: Celery broker/backend, rate limiting counters, job status caching.
"""

import redis

from app.core.config import get_settings

settings = get_settings()

redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
)


def get_redis() -> redis.Redis:
    """Return the shared Redis client instance."""
    return redis_client
