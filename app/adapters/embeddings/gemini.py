"""
Google Gemini Embedding Adapter.
Uses gemini-embedding-001 for cloud embeddings to reduce local resource usage.
"""

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import numpy as np

from app.adapters.base import BaseEmbedding
from app.core.config import settings
from app.core.exceptions import EmbeddingException

logger = logging.getLogger(__name__)


class GeminiEmbedding(BaseEmbedding):
    """Gemini embedding adapter for retrieval document/query embeddings."""

    def __init__(
        self,
        model_name: str = "models/gemini-embedding-001",
        normalize: bool = True,
        output_dimensionality: int = 768,
    ):
        self.model_name = model_name
        self.normalize = normalize
        self.output_dimensionality = output_dimensionality
        self._dimension = output_dimensionality
        self._client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        try:
            import google.generativeai as genai

            api_key = settings.google_api_key.strip()
            if not api_key or api_key == "replace-me":
                raise EmbeddingException(
                    "GOOGLE_API_KEY is required for Gemini embeddings",
                    error_code="EMBEDDING_MISSING_API_KEY",
                )

            genai.configure(api_key=api_key)
            self._client = genai
            logger.info("Gemini embedding client initialized: %s", self.model_name)

        except ImportError as e:
            raise EmbeddingException(
                "google-generativeai is not installed",
                error_code="EMBEDDING_IMPORT_ERROR",
                details={"error": str(e)},
            )

    def get_dimension(self) -> int:
        return self._dimension

    def _normalize_vec(self, vector: List[float]) -> List[float]:
        if not self.normalize:
            return vector
        arr = np.asarray(vector, dtype=np.float32)
        norm = float(np.linalg.norm(arr))
        if norm == 0:
            return vector
        return (arr / norm).tolist()

    def embed(self, text: str, normalize: bool = True) -> List[float]:
        """Embed a single query text (RETRIEVAL_QUERY task type)."""
        try:
            result = self._client.embed_content(
                model=self.model_name,
                content=text,
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=self.output_dimensionality,
            )
            vector = result["embedding"]
            if normalize:
                return self._normalize_vec(vector)
            return vector
        except Exception as e:
            raise EmbeddingException(
                f"Gemini query embedding failed: {str(e)}",
                error_code="EMBEDDING_ENCODE_FAILED",
                details={"error": str(e)},
            )

    def _embed_one_document(self, text: str) -> List[float]:
        """
        Embed a single document text (RETRIEVAL_DOCUMENT task type).
        Thread-safe: each call creates its own request, no shared state.
        """
        result = self._client.embed_content(
            model=self.model_name,
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=self.output_dimensionality,
        )
        vector = result["embedding"]
        return self._normalize_vec(vector) if self.normalize else vector

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = None,
        normalize: bool = True,
    ) -> List[List[float]]:
        """
        Embed a list of document texts in parallel using ThreadPoolExecutor.

        Strategy:
          - Split texts into chunks of `chunk_size` nodes.
          - Within each chunk, call the Gemini API concurrently (I/O-bound).
          - Collect results preserving original order.

        This replaces the old sequential for-loop which caused ~240s for 300 nodes.
        Expected speedup: ~16x on 8-core server (embed_parallelism=16).

        Args:
            texts:      List of text strings to embed.
            batch_size: Override chunk size (default: settings.ingestion_embedding_chunk_size).
            normalize:  Normalize vectors (ignored here; normalization set at init time).

        Returns:
            List of embedding vectors in the same order as input texts.
        """
        if not texts:
            return []

        # Determine parallelism from hardware profile (lazy import to avoid circular)
        from app.core.hardware import hardware

        chunk_size = batch_size or settings.ingestion_embedding_chunk_size
        parallelism = settings.ingestion_embed_parallelism or hardware.embed_parallelism
        total_chunks = math.ceil(len(texts) / chunk_size)

        all_vectors: List[List[float]] = []

        for chunk_idx, chunk_start in enumerate(range(0, len(texts), chunk_size)):
            chunk = texts[chunk_start : chunk_start + chunk_size]
            n_workers = min(len(chunk), parallelism)

            with ThreadPoolExecutor(max_workers=n_workers) as pool:
                # Submit all texts in this chunk concurrently
                future_to_idx = {
                    pool.submit(self._embed_one_document, text): i
                    for i, text in enumerate(chunk)
                }
                chunk_vecs: List[List[float]] = [None] * len(chunk)  # type: ignore[list-item]
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        chunk_vecs[idx] = future.result()
                    except Exception as e:
                        raise EmbeddingException(
                            f"Embedding failed for text index {chunk_start + idx}: {str(e)}",
                            error_code="EMBEDDING_BATCH_FAILED",
                            details={"chunk": chunk_idx, "index": idx, "error": str(e)},
                        )

            all_vectors.extend(chunk_vecs)
            logger.debug(
                "Embedded chunk %d/%d (%d texts, %d workers)",
                chunk_idx + 1, total_chunks, len(chunk), n_workers,
            )

        logger.info("embed_batch: %d texts embedded (%d chunks, parallelism=%d)",
                    len(texts), total_chunks, parallelism)
        return all_vectors
