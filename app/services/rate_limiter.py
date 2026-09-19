"""
Rate limiter — Redis-backed token bucket for upload endpoint.

Implements per-user rate limiting on document uploads to mitigate
denial-of-service via repeated uploads (Section 8).
"""

import logging
import time

from app.core.config import get_settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimitExceeded(Exception):
    """Raised when a user exceeds their rate limit."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class RateLimiter:
    """
    Redis-backed sliding window rate limiter.

    Uses a sorted set per user to track request timestamps.
    More precise than a simple counter, handles burst correctly.
    """

    def __init__(self, prefix: str = "ratelimit"):
        self.redis = get_redis()
        self.prefix = prefix
        self.max_requests = settings.RATE_LIMIT_UPLOADS_PER_MINUTE
        self.window_seconds = 60

    def _key(self, user_id: str) -> str:
        return f"{self.prefix}:upload:{user_id}"

    def check_rate_limit(self, user_id: str) -> None:
        """
        Check if the user has exceeded their upload rate limit.

        Uses a sliding window implemented with a Redis sorted set:
        - Each request adds a timestamp as score
        - Old entries (outside the window) are pruned
        - If remaining entries >= max_requests, limit is exceeded

        Raises:
            RateLimitExceeded: with retry_after in seconds
        """
        key = self._key(user_id)
        now = time.time()
        window_start = now - self.window_seconds

        pipe = self.redis.pipeline()

        # Remove entries outside the current window
        pipe.zremrangebyscore(key, 0, window_start)

        # Count entries in the current window
        pipe.zcard(key)

        # Add current request
        pipe.zadd(key, {str(now): now})

        # Set expiry on the key (cleanup if user stops uploading)
        pipe.expire(key, self.window_seconds * 2)

        results = pipe.execute()
        current_count = results[1]  # zcard result

        if current_count >= self.max_requests:
            # Find the oldest entry to calculate retry_after
            oldest = self.redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(self.window_seconds - (now - oldest[0][1])) + 1
            else:
                retry_after = self.window_seconds

            logger.warning(
                f"Rate limit exceeded for user {user_id}: "
                f"{current_count}/{self.max_requests} requests in {self.window_seconds}s"
            )
            raise RateLimitExceeded(retry_after=max(retry_after, 1))
