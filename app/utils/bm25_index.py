"""
BM25 Index Management — builds and persists vocabulary from document corpus.

This utility ensures that the VietnameseBM25Encoder has a stable vocabulary
of all terms seen in the corpus. It synchronizes the vocabulary with the
actual content stored in Qdrant.
"""

from __future__ import annotations

import asyncio
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
            logger.info(
                "BM25 vocab not found or empty at %s — will build on first query", settings.retrieval_bm25_vocab_path
            )

        _cached_encoder = encoder
        _cached_at = now
        return encoder


async def build_bm25_index_from_qdrant() -> int:
    """
    Build BM25 vocab from all chunks in Qdrant asynchronously.
    Offloads CPU-heavy tokenization and disk I/O to background threads.
    """
    from app.services.retrieval.retrieval_service import _get_vector_store

    vs = _get_vector_store()
    encoder = VietnameseBM25Encoder(vocab_path=settings.retrieval_bm25_vocab_path)

    batch_size = 500
    offset = None
    all_texts = []

    # Stage 1: Fetch all texts from Qdrant (Async I/O)
    while True:
        # Use the adapter's scroll method to ensure lazy-init and proper error handling
        points, next_offset = await vs.scroll(
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vector=False,
        )
        if not points:
            break

        for point in points:
            text = (point.get("payload") or {}).get("text", "")
            if text:
                all_texts.append(text)

        if next_offset is None:
            break
        offset = next_offset

    logger.info("Fetched %d chunks from Qdrant for BM25 rebuild", len(all_texts))

    if not all_texts:
        # No documents left — clear stale vocab
        if os.path.exists(settings.retrieval_bm25_vocab_path):
            try:
                await asyncio.to_thread(os.remove, settings.retrieval_bm25_vocab_path)
                logger.info("BM25 vocab cleared (no chunks in Qdrant)")
            except OSError as e:
                logger.warning("Failed to remove BM25 vocab file: %s", e)

        global _cached_encoder, _cached_at
        _cached_encoder = None
        _cached_at = 0
        return 0

    # Stage 2: CPU-heavy Vocab Building (Offload to Thread)
    def _fit_task():
        for text in all_texts:
            tokens = encoder.tokenize(text)
            for t in tokens:
                encoder._get_or_create_id(t)
        encoder.save()
        return len(encoder.vocab)

    vocab_size = await asyncio.to_thread(_fit_task)

    # Stage 3: Update local cache immediately
    _cached_encoder = encoder
    _cached_at = time.monotonic()

    logger.info("BM25 vocabulary built and saved: %d terms", vocab_size)
    return vocab_size


async def update_bm25_index(new_texts: list[str]) -> None:
    """Update BM25 index with new document chunks."""
    if not new_texts:
        return
    await build_bm25_index_from_qdrant()


async def save_bm25_vocab_async(encoder: VietnameseBM25Encoder) -> None:
    """Save vocabulary to disk asynchronously."""
    await asyncio.to_thread(encoder.save)


async def load_bm25_vocab_async(encoder: VietnameseBM25Encoder) -> bool:
    """Load vocabulary from disk asynchronously."""
    return await asyncio.to_thread(encoder.load)
