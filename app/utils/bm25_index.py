"""
BM25 Index Management — builds and persists vocabulary from document corpus.

Builds BM25 vocab + IDF from all chunks in Qdrant, persists to disk.
Called during startup (lazy) or after document ingestion.
"""

from __future__ import annotations

import logging
import os
import threading
import time

from app.adapters.sparse_embeddings.vietnamese_bm25 import VietnameseBM25Encoder
from app.core.config import settings

logger = logging.getLogger(__name__)

_VOCAB_PATH = "data/bm25_vocab.json"
_VOCAB_TTL = 120.0  # Reload vocab every 2 minutes to pick up new documents

_cached_encoder: VietnameseBM25Encoder | None = None
_cached_at: float = 0.0
_encoder_lock = threading.Lock()


def get_bm25_encoder() -> VietnameseBM25Encoder:
    """Get or create the BM25 encoder with TTL-based reload.

    Tries to load from disk first. If no vocab file exists,
    returns an encoder with empty vocab (will be built on first use).
    Reloads from disk every _VOCAB_TTL seconds to pick up changes
    made by the Celery worker after document upload.
    """
    global _cached_encoder, _cached_at

    with _encoder_lock:
        now = time.monotonic()
        if _cached_encoder is not None and (now - _cached_at) < _VOCAB_TTL:
            return _cached_encoder

        encoder = VietnameseBM25Encoder(
            k1=settings.retrieval_bm25_k1,
            b=settings.retrieval_bm25_b,
        )
        loaded = encoder.load(_VOCAB_PATH)
        if not loaded:
            if _cached_encoder is not None:
                return _cached_encoder
            logger.info("BM25 vocab not found at %s — will build on first query", _VOCAB_PATH)

        _cached_encoder = encoder
        _cached_at = now
        return encoder


def build_bm25_index_from_qdrant() -> int:
    """Build BM25 vocab from all chunks in Qdrant.

    Scrolls through all points, extracts text, builds vocab + IDF.
    Persists to data/bm25_vocab.json.

    Returns number of terms in vocabulary.

    Raises:
        Exception: If Qdrant scroll fails or vocab build fails.
    """
    from app.services.retrieval.retrieval_service import _get_vector_store

    vs = _get_vector_store()

    # Build fresh encoder (bypass cache)
    encoder = VietnameseBM25Encoder(
        k1=settings.retrieval_bm25_k1,
        b=settings.retrieval_bm25_b,
    )

    # Scroll all chunks from Qdrant via client directly
    all_texts: list[str] = []
    batch_size = 500
    offset = None

    logger.info("Building BM25 index from Qdrant...")
    while True:
        results = vs.client.scroll(
            collection_name=vs.collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points, next_offset = results
        if not points:
            break
        for point in points:
            text = (point.payload or {}).get("text", "")
            if text:
                all_texts.append(text)
        if next_offset is None:
            break
        offset = next_offset

    logger.info("Scrolled %d chunks from Qdrant", len(all_texts))

    if not all_texts:
        # No documents left — clear stale vocab so queries skip BM25
        if os.path.exists(_VOCAB_PATH):
            try:
                os.remove(_VOCAB_PATH)
                logger.info("BM25 vocab cleared (no chunks in Qdrant)")
            except OSError as e:
                logger.warning("Failed to remove BM25 vocab file: %s", e)
        # Force reload on next get_bm25_encoder() call
        global _cached_encoder, _cached_at
        _cached_encoder = None
        _cached_at = 0
        return 0

    encoder.build_vocab_and_idf(all_texts)
    encoder.save(_VOCAB_PATH)

    # Update cache immediately so API process has fresh vocab
    _cached_encoder = encoder
    _cached_at = time.monotonic()

    logger.info("BM25 index built: %d terms from %d docs", len(encoder.vocab), encoder.doc_count)
    return len(encoder.vocab)


def update_bm25_index(new_texts: list[str]) -> None:
    """Update BM25 index with new document chunks.

    Triggers a full rebuild from Qdrant for correct IDF.
    Called after document ingestion.

    Raises:
        Exception: If rebuild fails.
    """
    if not new_texts:
        return
    build_bm25_index_from_qdrant()
