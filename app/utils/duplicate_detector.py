"""
Duplicate Detector: Redis Bloom Filter for O(1) existence checks.
Supports both Async (FastAPI) and Sync (Celery) clients.
"""

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Uses Redis Bloom module for duplicate detection."""

    KEY = "bf:document:sha256"
    ERROR_RATE = 0.01
    CAPACITY = 100000

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            raise ValueError("redis_client is required for DuplicateDetector")
        self._r = client
        self._filter_ready = False

    # ── Async Methods ────────────────────────────────────────────────

    async def _ensure_filter(self) -> None:
        """Initialize Bloom Filter (Async)."""
        try:
            await self._r.execute_command("BF.RESERVE", self.KEY, self.ERROR_RATE, self.CAPACITY)
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.debug("Bloom filter reservation skipped (Async): %s", e)

    async def exists(self, sha256: str) -> bool:
        """Check if SHA256 likely exists (Async)."""
        if not self._filter_ready:
            await self._ensure_filter()
            self._filter_ready = True
        try:
            res = await self._r.execute_command("BF.EXISTS", self.KEY, sha256)
            return res == 1
        except Exception:
            return False

    async def add(self, sha256: str) -> None:
        """Add SHA256 to the detector (Async)."""
        try:
            await self._r.execute_command("BF.ADD", self.KEY, sha256)
        except Exception:
            pass

    # ── Sync Methods (For Workers) ──────────────────────────────────

    def _ensure_filter_sync(self) -> None:
        """Initialize Bloom Filter (Sync)."""
        try:
            self._r.execute_command("BF.RESERVE", self.KEY, self.ERROR_RATE, self.CAPACITY)
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.debug("Bloom filter reservation skipped (Sync): %s", e)

    def exists_sync(self, sha256: str) -> bool:
        """Check if SHA256 likely exists (Sync)."""
        if not self._filter_ready:
            self._ensure_filter_sync()
            self._filter_ready = True
        try:
            res = self._r.execute_command("BF.EXISTS", self.KEY, sha256)
            return res == 1
        except Exception:
            return False

    def add_sync(self, sha256: str) -> None:
        """Add SHA256 to the detector (Sync)."""
        try:
            self._r.execute_command("BF.ADD", self.KEY, sha256)
        except Exception:
            pass
