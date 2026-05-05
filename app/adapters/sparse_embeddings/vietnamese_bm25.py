"""
Vietnamese BM25 Sparse Encoder for Qdrant Hybrid Search.

Optimized Implementation:
- Word segmentation using Underthesea.
- Minimalist client-side logic: Produces Raw Term Frequencies (TF).
- Server-side IDF: Designed to work with Qdrant's Modifier.IDF for scalable, real-time BM25.
- Robust Vocabulary: Mapping strings to stable integer IDs.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any
from underthesea import word_tokenize


# --- Performance Optimization: Tokenizer Cache ---
@lru_cache(maxsize=10000)
def _cached_tokenize(text: str) -> list[str]:
    """
    Cached Vietnamese word segmentation to reduce CPU load under high concurrency.
    Size 10k covers typical query vocabulary and recent document chunks.
    """
    return word_tokenize(text)


logger = logging.getLogger(__name__)

# Comprehensive Vietnamese stop words list
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
    Modern Vietnamese BM25 Encoder.

    Acts as a bridge between Vietnamese text and Qdrant's sparse vector engine.
    Instead of calculating IDF client-side (which is hard to scale), it sends
    token counts to Qdrant, which then applies server-side IDF (Modifier.IDF).
    """

    def __init__(self, vocab_path: str | Path = "data/bm25_vocab.json") -> None:
        self.vocab_path = Path(vocab_path)
        self.vocab: dict[str, int] = {}
        self._next_id: int = 0
        self.load()

    def tokenize(self, text: str) -> list[str]:
        """
        Segment Vietnamese text and clean tokens.
        - Uses underthesea for word segmentation (word_1 word_2 format).
        - Strips punctuation and digits.
        - Removes stop words.
        """
        if not text or not text.strip():
            return []

        # Segment words (e.g., "hợp đồng kinh tế" -> "hợp_đồng kinh_tế")
        try:
            segmented = word_tokenize(text, format="text")
        except Exception as e:
            logger.warning("Tokenization failed: %s. Falling back to simple split.", e)
            segmented = text

        # Clean tokens: lower, remove punctuation/digits, filter short/stop words
        tokens = []
        # Match only alphanumeric and underscores (word segments)
        for t in re.findall(r"\w+", segmented.lower()):
            if t not in _VIETNAMESE_STOP_WORDS and len(t) > 1 and not t.isnumeric():
                tokens.append(t)

        return tokens

    def _get_or_create_id(self, term: str) -> int:
        """Map term to integer ID, updating vocab if new."""
        if term not in self.vocab:
            self.vocab[term] = self._next_id
            self._next_id += 1
        return self.vocab[term]

    def encode(self, text: str) -> dict[str, Any]:
        """
        Encode text into a sparse representation (indices and term frequencies).

        Note: We return Raw Term Frequency (TF). Qdrant's Modifier.IDF will
        automatically multiply this by the server-side IDF at search time.
        """
        tokens = self.tokenize(text)
        if not tokens:
            return {"indices": [], "values": []}

        counts = Counter(tokens)

        # Sort by index for Qdrant consistency
        raw_indices = [(self._get_or_create_id(term), count) for term, count in counts.items()]
        raw_indices.sort(key=lambda x: x[0])

        return {"indices": [idx for idx, _ in raw_indices], "values": [float(count) for _, count in raw_indices]}

    def encode_sparse_vector(self, text: str) -> Any:
        """Helper to create a Qdrant SparseVector directly."""
        data = self.encode(text)
        if not data["indices"]:
            return None

        from qdrant_client.models import SparseVector

        return SparseVector(indices=data["indices"], values=data["values"])

    def encode_batch_sparse_vectors(self, texts: list[str]) -> list[Any]:
        """Batch encoding helper."""
        return [self.encode_sparse_vector(t) for t in texts]

    # ── Persistence ───────────────────────────────────────────────

    def save(self) -> None:
        """Save vocabulary to JSON file."""
        if not self.vocab:
            return

        try:
            self.vocab_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"vocab": self.vocab, "next_id": self._next_id}
            self.vocab_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("BM25 vocabulary saved: %d terms to %s", len(self.vocab), self.vocab_path)
        except Exception as e:
            logger.error("Failed to save BM25 vocab: %s", e)

    def load(self) -> bool:
        """Load vocabulary from JSON file."""
        if not self.vocab_path.exists():
            return False

        try:
            data = json.loads(self.vocab_path.read_text(encoding="utf-8"))
            self.vocab = data.get("vocab", {})
            self._next_id = data.get("next_id", len(self.vocab))
            logger.info("BM25 vocabulary loaded: %d terms from %s", len(self.vocab), self.vocab_path)
            return True
        except Exception as e:
            logger.warning("Failed to load BM25 vocab: %s", e)
            return False

    @property
    def is_ready(self) -> bool:
        """Vocab is considered ready if it has any terms."""
        return len(self.vocab) > 0
