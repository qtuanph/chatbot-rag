"""
Duplicate Detector: Redis Bloom Filter for O(1) existence checks.
Used to skip DB queries during high-concurrency uploads.
"""

from __future__ import annotations
import logging
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Uses Redis Bloom module for duplicate detection."""

    KEY = "bf:document:sha256"
    ERROR_RATE = 0.01
    CAPACITY = 100000

    def __init__(self, client: redis.Redis) -> None:
        self._r = client
        try:
            # Try to reserve the bloom filter on init (ignore errors if already exists)
            self._ensure_filter()
        except Exception:
            pass

    async def _ensure_filter(self) -> None:
        """Initialize Bloom Filter if not exists."""
        try:
            # BF.RESERVE: Create the filter with specific capacity and error rate
            await self._r.execute_command("BF.RESERVE", self.KEY, self.ERROR_RATE, self.CAPACITY)
        except Exception as e:
            # If already exists, it will error; we skip it
            if "already exists" not in str(e).lower():
                logger.debug("Bloom filter reservation skipped: %s", e)

    async def exists(self, sha256: str) -> bool:
        """Check if SHA256 likely exists."""
        try:
            # BF.EXISTS returns 1 if likely exists, 0 if definitely does not
            res = await self._r.execute_command("BF.EXISTS", self.KEY, sha256)
            return res == 1
        except Exception:
            # Fallback to DB check (handled by service)
            return False

    async def add(self, sha256: str) -> None:
        """Add SHA256 to the detector."""
        try:
            await self._r.execute_command("BF.ADD", self.KEY, sha256)
        except Exception:
            pass
