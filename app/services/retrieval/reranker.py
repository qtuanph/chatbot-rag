"""
Vietnamese Cross-Encoder Reranker — re-ranks retrieved chunks for precision.

Uses AITeamVN/Vietnamese_Reranker (MRR@10=0.8672 on Legal Zalo benchmark).
Same org as the embedding model (AITeamVN/Vietnamese_Embedding_v2).

Pipeline: dense+BM25 hybrid candidates → cross-encoder rerank → top-k for LLM context.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_reranker() -> VietnameseReranker:
    """Get or create the singleton reranker instance.

    Raises ImportError if sentence-transformers is not installed.
    Raises RuntimeError if model fails to load.
    """
    return VietnameseReranker()


class VietnameseReranker:
    """Cross-encoder reranker using AITeamVN/Vietnamese_Reranker.

    Takes (query, passage) pairs and produces relevance scores.
    More accurate than bi-encoder similarity for final ranking.
    """

    def __init__(self):
        from sentence_transformers import CrossEncoder

        model_name = settings.retrieval_rerank_model
        logger.info("Loading reranker model: %s ...", model_name)
        self.model = CrossEncoder(
            model_name,
            device="cpu",
            max_length=2304,  # 256 query + 2048 passage
        )
        logger.info("Reranker model loaded: %s", model_name)

    def rerank(
        self,
        query: str,
        documents: list,
        text_attr: str = "full_text",
        top_k: int | None = None,
    ) -> list:
        """Re-rank documents by cross-encoder relevance scores.

        Args:
            query: User query string
            documents: List of document objects (RagNode or RetrievedDocument)
            text_attr: Attribute name to get text from document object
            top_k: Number of results to return (default: from settings)

        Returns:
            Documents sorted by reranker score descending, truncated to top_k

        Raises:
            ValueError: If documents list is empty
            RuntimeError: If model prediction fails
        """
        if not documents:
            raise ValueError("Cannot rerank empty document list")

        top_k = top_k or settings.retrieval_rerank_top_k

        # Build (query, passage) pairs for cross-encoder
        pairs = []
        for doc in documents:
            text = getattr(doc, text_attr, None) or ""
            pairs.append((query, text))

        # Cross-encoder scoring
        scores = self.model.predict(pairs, batch_size=32)

        # Attach scores and sort
        scored_docs = list(zip(documents, scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        # Update score attributes on the document objects
        result = []
        for doc, score in scored_docs[:top_k]:
            if hasattr(doc, "score"):
                doc.score = float(score)
            result.append(doc)

        logger.info(
            "Reranked %d documents → top %d (best_score=%.4f)",
            len(documents), len(result),
            scored_docs[0][1] if scored_docs else 0,
        )
        return result
