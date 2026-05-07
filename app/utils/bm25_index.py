import logging
from typing import Any

from app.adapters.sparse_embeddings.vietnamese_bm25 import VietnameseBM25Encoder
from app.core.config import settings

logger = logging.getLogger(__name__)


class BM25Manager:
    """Helper to manage BM25 encoder lifecycle with Redis."""

    @staticmethod
    def get_encoder(redis_client: Any) -> VietnameseBM25Encoder:
        """Get encoder and load vocab synchronously."""
        encoder = VietnameseBM25Encoder(redis_client=redis_client)
        encoder.load_sync()
        return encoder

    @staticmethod
    async def get_encoder_async(redis_client: Any) -> VietnameseBM25Encoder:
        """Get encoder and load vocab asynchronously."""
        encoder = VietnameseBM25Encoder(redis_client=redis_client)
        await encoder.load_async()
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
    # Start fresh if rebuilding
    encoder.vocab = {}
    encoder._next_id = 0

    batch_size = 500
    offset = None
    all_texts = []

    # Stage 1: Fetch all texts from Qdrant
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
            text = point.payload.get("content") or point.payload.get("text")
            if text:
                all_texts.append(text)

        offset = next_offset
        if not offset:
            break

    if not all_texts:
        logger.warning("No texts found in Qdrant for BM25 rebuild")
        return 0

    # Stage 2: Tokenize and build vocab
    # This can be CPU heavy, but for smaller/medium datasets it's fine
    for i, text in enumerate(all_texts):
        encoder.tokenize(text)  # Populate internal Counter if we had one, but our encoder builds on the fly
        # In our case, encode() actually populates the vocab
        encoder.encode(text)

        if i % 1000 == 0:
            logger.info("BM25 Rebuild: Processed %d/%d documents", i, len(all_texts))

    # Stage 3: Save to Redis
    await encoder.save_async()
    logger.info("BM25 rebuild complete. Vocab size: %d", len(encoder.vocab))
    return len(all_texts)


def get_bm25_encoder(redis_client: Any) -> VietnameseBM25Encoder:
    """Alias for backward compatibility (Sync)."""
    return BM25Manager.get_encoder(redis_client)


async def get_async_bm25_encoder(redis_client: Any) -> VietnameseBM25Encoder:
    """Alias for backward compatibility (Async)."""
    return await BM25Manager.get_encoder_async(redis_client)
