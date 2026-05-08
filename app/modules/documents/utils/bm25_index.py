import logging
import time
from typing import Any

from app.adapters.sparse_embeddings.vietnamese_bm25 import VietnameseBM25Encoder
from app.core.config import settings

logger = logging.getLogger(__name__)


class BM25Manager:
    """
    Helper to manage BM25 encoder lifecycle with Redis.
    Uses a TTL-cached Singleton pattern to handle 200+ CCU without Redis bottleneck.
    """

    _instance: VietnameseBM25Encoder | None = None
    _last_load_time: float = 0
    _ttl: float = settings.bm25_singleton_ttl

    @classmethod
    async def get_encoder_async(cls, redis_client: Any) -> VietnameseBM25Encoder:
        """Get encoder and load vocab asynchronously with in-memory caching."""
        current_time = time.time()

        if cls._instance and (current_time - cls._last_load_time < cls._ttl):
            return cls._instance

        logger.info("[PERF] Loading BM25 vocabulary into in-memory singleton...")
        encoder = VietnameseBM25Encoder(redis_client=redis_client)
        await encoder.load_async()

        cls._instance = encoder
        cls._last_load_time = current_time
        return encoder

    @classmethod
    def get_encoder(cls, redis_client: Any) -> VietnameseBM25Encoder:
        """Get encoder and load vocab synchronously (for workers)."""
        current_time = time.time()

        if cls._instance and (current_time - cls._last_load_time < cls._ttl):
            return cls._instance

        encoder = VietnameseBM25Encoder(redis_client=redis_client)
        encoder.load_sync()

        cls._instance = encoder
        cls._last_load_time = current_time
        return encoder


async def build_bm25_index_from_qdrant(redis_client: Any) -> int:
    """
    Build BM25 vocab from all chunks in Qdrant asynchronously.
    """
    from app.adapters.vector_stores.qdrant import QdrantVectorStore

    vs = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=settings.qdrant_collection,
        vector_size=settings.embedding_vector_size,
    )

    encoder = VietnameseBM25Encoder(redis_client=redis_client)
    encoder.vocab = {}
    encoder._next_id = 0

    batch_size = settings.retrieval_bm25_rebuild_batch_size
    offset = None
    all_texts = []

    logger.info("Starting BM25 rebuild from Qdrant...")
    while True:
        points, next_offset = await vs.scroll(
            limit=batch_size,
            offset=offset,
            with_payload=True,
        )
        if not points:
            break

        for point in points:
            payload = getattr(point, "payload", None) or point.get("payload", {})
            text = payload.get("content") or payload.get("text")
            if text:
                all_texts.append(text)

        offset = next_offset
        if not offset:
            break

    if not all_texts:
        logger.warning("No texts found in Qdrant for BM25 rebuild")
        return 0

    for i, text in enumerate(all_texts):
        encoder.tokenize(text)
        encoder.encode(text)

        if i % 1000 == 0:
            logger.info("BM25 Rebuild: Processed %d/%d documents", i, len(all_texts))

    await encoder.save_async()
    logger.info("BM25 rebuild complete. Vocab size: %d", len(encoder.vocab))
    return len(all_texts)


def get_bm25_encoder(redis_client: Any) -> VietnameseBM25Encoder:
    """Alias for backward compatibility (Sync)."""
    return BM25Manager.get_encoder(redis_client)


async def get_async_bm25_encoder(redis_client: Any) -> VietnameseBM25Encoder:
    """Alias for backward compatibility (Async)."""
    return await BM25Manager.get_encoder_async(redis_client)
