"""
BM25 Index Management — builds and persists vocabulary from document corpus.

Builds BM25 vocab + IDF from all chunks in Qdrant, persists to disk.
Called during startup (lazy) or after document ingestion.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from app.adapters.sparse_embeddings.vietnamese_bm25 import VietnameseBM25Encoder
from app.core.config import settings

logger = logging.getLogger(__name__)

_VOCAB_PATH = "data/bm25_vocab.json"


@lru_cache(maxsize=1)
def get_bm25_encoder() -> VietnameseBM25Encoder:
    """Get or create the singleton BM25 encoder.

    Tries to load from disk first. If no vocab file exists,
    returns an encoder with empty vocab (will be built on first use).
    """
    encoder = VietnameseBM25Encoder(
        k1=settings.retrieval_bm25_k1,
        b=settings.retrieval_bm25_b,
    )
    loaded = encoder.load(_VOCAB_PATH)
    if not loaded:
        logger.info("BM25 vocab not found at %s — will build on first query", _VOCAB_PATH)
    return encoder


def build_bm25_index_from_qdrant() -> int:
    """Build BM25 vocab from all chunks in Qdrant.

    Scrolls through all points, extracts text, builds vocab + IDF.
    Persists to data/bm25_vocab.json.

    Returns number of terms in vocabulary.

    Raises:
        Exception: If Qdrant scroll fails or vocab build fails.
    """
    from app.services.retrieval.rag import _get_vector_store

    vs = _get_vector_store()
    encoder = get_bm25_encoder()

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
        raise ValueError(
            "No chunks found in Qdrant — cannot build BM25 index. "
            "Upload documents first."
        )

    encoder.build_vocab_and_idf(all_texts)
    encoder.save(_VOCAB_PATH)

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
