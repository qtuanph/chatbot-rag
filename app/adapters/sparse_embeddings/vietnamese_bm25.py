"""
Vietnamese BM25 Sparse Encoder for Qdrant Hybrid Search.

Optimized Implementation:
- Word segmentation using Underthesea.
- Minimalist client-side logic: Produces Raw Term Frequencies (TF).
- Server-side IDF: Designed to work with Qdrant's Modifier.IDF for scalable, real-time BM25.
- Robust Vocabulary: Mapping strings to stable integer IDs, persisted in Redis.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import Counter
from functools import lru_cache
from typing import Any

from underthesea import word_tokenize

# --- Force Preload Underthesea Model ---
try:
    word_tokenize("khởi tạo", format="text")
except Exception:
    pass


@lru_cache(maxsize=10000)
def _cached_tokenize(text: str) -> list[str]:
    return word_tokenize(text)


logger = logging.getLogger(__name__)

_VIETNAMESE_STOP_WORDS: frozenset[str] = frozenset(
    {
        "và",
        "của",
        "là",
        "có",
        "không",
        "được",
        "trong",
        "với",
        "cho",
        "này",
        "đó",
        "những",
        "từ",
        "để",
        "một",
        "các",
        "về",
        "nếu",
        "thì",
        "đã",
        "sẽ",
        "đang",
        "vẫn",
        "phải",
        "nên",
        "bị",
        "bởi",
        "vì",
        "nhưng",
        "hay",
        "hoặc",
        "thành",
        "ra",
        "vào",
        "lên",
        "xuống",
        "lại",
        "mà",
        "cũng",
        "đều",
        "nào",
        "đâu",
        "sao",
        "thế",
        "khi",
        "nơi",
        "vậy",
        "gì",
        "ai",
        "bao_giờ",
        "tại",
        "theo",
        "cùng",
        "nữa",
        "rất",
        "hơn",
        "nhất",
        "mỗi",
        "tất_cả",
        "riêng",
        "khác",
        "như",
        "thường",
        "lúc",
        "ngay",
        "chỉ",
        "từng",
        "vừa",
        "mới",
        "luôn",
        "tự",
        "tới",
        "đến",
        "hầu_hết",
        "chưa",
        "chẳng",
        "biết",
        "thấy",
        "làm",
        "đi",
        "cái",
        "con",
        "chiếc",
        "sự",
        "việc",
        "nhà",
        "người",
        "anh",
        "chị",
        "em",
        "ông",
        "bà",
        "bạn",
        "họ",
        "mình",
        "ta",
        "tôi",
        "chúng_ta",
        "chúng_tôi",
        "chúng_họ",
        "đây",
        "kia",
        "ấy",
        "nay",
        "vừa_qua",
        "trước",
        "sau",
        "vừa_mới",
        "vừa_xong",
    }
)


class VietnameseBM25Encoder:
    """
    Modern Vietnamese BM25 Encoder with Redis-backed vocabulary.
    Ensures consistency across multiple worker containers.
    """

    REDIS_KEY = "rag:bm25:vocab"

    def __init__(self, redis_client: Any) -> None:
        """
        Initialize with a redis_client (Sync or Async).
        Vocab is loaded lazily or on demand.
        """
        self._redis = redis_client
        self.vocab: dict[str, int] = {}
        self._next_id: int = 0
        self._is_async = hasattr(redis_client, "get") and asyncio.iscoroutinefunction(redis_client.get)

    def tokenize(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        try:
            segmented = word_tokenize(text, format="text")
        except Exception as e:
            logger.warning("Tokenization failed: %s", e)
            segmented = text

        tokens = []
        for t in re.findall(r"\w+", segmented.lower()):
            if t not in _VIETNAMESE_STOP_WORDS and len(t) > 1 and not t.isnumeric():
                tokens.append(t)
        return tokens

    def _get_or_create_id(self, term: str) -> int:
        if term not in self.vocab:
            self.vocab[term] = self._next_id
            self._next_id += 1
        return self.vocab[term]

    def encode(self, text: str) -> dict[str, Any]:
        tokens = self.tokenize(text)
        if not tokens:
            return {"indices": [], "values": []}

        counts = Counter(tokens)
        raw_indices = [(self._get_or_create_id(term), count) for term, count in counts.items()]
        raw_indices.sort(key=lambda x: x[0])

        return {"indices": [idx for idx, _ in raw_indices], "values": [float(count) for _, count in raw_indices]}

    def encode_sparse_vector(self, text: str) -> Any:
        data = self.encode(text)
        if not data["indices"]:
            return None
        from qdrant_client.models import SparseVector

        return SparseVector(indices=data["indices"], values=data["values"])

    def encode_batch_sparse_vectors(self, texts: list[str]) -> list[Any]:
        return [self.encode_sparse_vector(t) for t in texts]

    # ── Persistence (Redis) ───────────────────────────────────────

    async def load_async(self, max_retries: int = 3) -> bool:
        """Load vocabulary from Redis (Async) with retry."""
        for attempt in range(max_retries):
            try:
                raw = await self._redis.get(self.REDIS_KEY)
                if raw:
                    data = json.loads(raw)
                    self.vocab = data.get("vocab", {})
                    self._next_id = data.get("next_id", len(self.vocab))
                    if self.vocab:
                        logger.info("BM25 vocab loaded: %d terms", len(self.vocab))
                        return True
                    logger.warning("BM25 vocab in Redis is empty")
                    return False
                if attempt == 0:
                    logger.warning("BM25 vocab key '%s' not found in Redis", self.REDIS_KEY)
                return False
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = 0.5 * (2 ** attempt)
                    logger.warning(
                        "BM25 vocab load failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, max_retries, delay, e,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("BM25 vocab load failed after %d attempts: %s", max_retries, e)
        return False

    def load_sync(self, max_retries: int = 3) -> bool:
        """Load vocabulary from Redis (Sync) with retry."""
        import time as _time
        for attempt in range(max_retries):
            try:
                raw = self._redis.get(self.REDIS_KEY)
                if raw:
                    data = json.loads(raw)
                    self.vocab = data.get("vocab", {})
                    self._next_id = data.get("next_id", len(self.vocab))
                    if self.vocab:
                        logger.info("BM25 vocab loaded: %d terms", len(self.vocab))
                        return True
                    logger.warning("BM25 vocab in Redis is empty")
                    return False
                if attempt == 0:
                    logger.warning("BM25 vocab key '%s' not found in Redis", self.REDIS_KEY)
                return False
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = 0.5 * (2 ** attempt)
                    logger.warning(
                        "BM25 vocab load failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, max_retries, delay, e,
                    )
                    _time.sleep(delay)
                else:
                    logger.error("BM25 vocab load failed after %d attempts: %s", max_retries, e)
        return False

    async def save_async(self) -> None:
        """Save vocabulary to Redis (Async)."""
        if not self.vocab:
            return
        try:
            data = {"vocab": self.vocab, "next_id": self._next_id}
            await self._redis.set(self.REDIS_KEY, json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.error("Failed to save BM25 vocab to Redis (Async): %s", e)

    def save_sync(self) -> None:
        """Save vocabulary to Redis (Sync)."""
        if not self.vocab:
            return
        try:
            data = {"vocab": self.vocab, "next_id": self._next_id}
            self._redis.set(self.REDIS_KEY, json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.error("Failed to save BM25 vocab to Redis (Sync): %s", e)

    @property
    def is_ready(self) -> bool:
        return len(self.vocab) > 0
