"""
Google Gemini Embedding Adapter.
Uses gemini-embedding-001 for cloud embeddings to reduce local resource usage.
"""

import logging
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

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> List[List[float]]:
        vectors: List[List[float]] = []
        try:
            for text in texts:
                result = self._client.embed_content(
                    model=self.model_name,
                    content=text,
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=self.output_dimensionality,
                )
                vector = result["embedding"]
                if normalize:
                    vector = self._normalize_vec(vector)
                vectors.append(vector)
            return vectors
        except Exception as e:
            raise EmbeddingException(
                f"Gemini batch embedding failed: {str(e)}",
                error_code="EMBEDDING_BATCH_FAILED",
                details={"batch_size": len(texts), "error": str(e)},
            )
