"""
BM25 Index Management — builds and persists vocabulary from document corpus.

This utility ensures that the VietnameseBM25Encoder has a stable vocabulary
of all terms seen in the corpus. It synchronizes the vocabulary with the
actual content stored in Qdrant.
"""

from __future__ import annotations

import logging
import os
import threading
import time

from app.adapters.sparse_embeddings.vietnamese_bm25 import VietnameseBM25Encoder
from app.core.config import settings

logger = logging.getLogger(__name__)


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
        if _cached_encoder is not None and (now - _cached_at) < settings.retrieval_bm25_vocab_ttl:
            return _cached_encoder

        # Modern encoder handles its own persistence path
        encoder = VietnameseBM25Encoder(vocab_path=settings.retrieval_bm25_vocab_path)
        
        # encoder.load() is called in __init__, but we check if it actually has data
        if not encoder.is_ready:
            if _cached_encoder is not None:
                return _cached_encoder
            logger.info("BM25 vocab not found or empty at %s — will build on first query", settings.retrieval_bm25_vocab_path)

        _cached_encoder = encoder
        _cached_at = now
        return encoder


async def build_bm25_index_from_qdrant() -> int:
    """Build BM25 vocab from all chunks in Qdrant."""
    from app.services.retrieval.retrieval_service import _get_vector_store

    vs = _get_vector_store()
    encoder = VietnameseBM25Encoder(vocab_path=settings.retrieval_bm25_vocab_path)

    batch_size = 500
    offset = None
    processed_count = 0

    while True:
        results = await vs.client.scroll(
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
                # Tokenization internally updates the vocab mapping
                tokens = encoder.tokenize(text)
                for t in tokens:
                    encoder._get_or_create_id(t)
                processed_count += 1
                
        if next_offset is None:
            break
        offset = next_offset

    logger.info("Processed %d chunks from Qdrant", processed_count)

    if processed_count == 0:
        # No documents left — clear stale vocab
        if os.path.exists(settings.retrieval_bm25_vocab_path):
            try:
                os.remove(settings.retrieval_bm25_vocab_path)
                logger.info("BM25 vocab cleared (no chunks in Qdrant)")
            except OSError as e:
                logger.warning("Failed to remove BM25 vocab file: %s", e)
        
        global _cached_encoder, _cached_at
        _cached_encoder = None
        _cached_at = 0
        return 0

    encoder.save()

    # Update cache immediately so API process has fresh vocab
    _cached_encoder = encoder
    _cached_at = time.monotonic()

    logger.info("BM25 vocabulary built: %d terms mapping saved", len(encoder.vocab))
    return len(encoder.vocab)


async def update_bm25_index(new_texts: list[str]) -> None:
    """Update BM25 index with new document chunks."""
    if not new_texts:
        return
    await build_bm25_index_from_qdrant()
