"""Request queue manager.

Caps simultaneous LLM requests so we don't slam the Gemini API with
unbounded concurrency (rate-limit friendly, avoids 429s).
"""

import asyncio
import redis.asyncio as redis
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("queue")
settings = get_settings()

# Gemini free-tier is ~15 RPM. Raise this if you're on paid quota.
MAX_CONCURRENT = 8


class QueueManager:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self.redis: redis.Redis | None = None
        self.active_requests = 0

    async def connect(self):
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def disconnect(self):
        if self.redis:
            await self.redis.close()

    async def acquire(self, session_id: str, timeout: float = 30.0) -> bool:
        """Wait for a slot to become available.

        Returns True if slot acquired, False if timeout.
        """
        try:
            acquired = await asyncio.wait_for(
                self.semaphore.acquire(), timeout=timeout
            )
            self.active_requests += 1
            logger.debug(f"Slot acquired for {session_id}. Active: {self.active_requests}/{MAX_CONCURRENT}")
            return acquired
        except asyncio.TimeoutError:
            logger.warning(f"Queue timeout for {session_id}")
            return False

    def release(self, session_id: str):
        """Release a slot after request completes."""
        self.semaphore.release()
        self.active_requests = max(0, self.active_requests - 1)
        logger.debug(f"Slot released for {session_id}. Active: {self.active_requests}/{MAX_CONCURRENT}")

    @property
    def queue_status(self) -> dict:
        return {
            "active_requests": self.active_requests,
            "max_concurrent": MAX_CONCURRENT,
            "available_slots": MAX_CONCURRENT - self.active_requests,
        }


# Singleton
queue_manager = QueueManager()
