"""
SentenceTransformer Embedding Adapter — Local/Offline.

Wraps HuggingFace SentenceTransformer models for on-premise embedding.
Default model: AITeamVN/Vietnamese_Embedding_v2 (1024-dim, Vietnamese-optimized).
GPU: PyTorch fp16. CPU: ONNX runtime (2-3x faster than PyTorch fp32).
"""

import logging

from app.adapters.base import BaseEmbedding
from app.core.hardware import hardware

logger = logging.getLogger(__name__)


class SentenceTransformerEmbedding(BaseEmbedding):
    """
    Local embedding adapter using HuggingFace SentenceTransformer.

    Supports any sentence-transformers-compatible model.
    GPU is used automatically when available (torch.cuda).
    """

    def __init__(
        self,
        model_name: str = "AITeamVN/Vietnamese_Embedding_v2",
        normalize: bool = True,
        batch_size: int = 32,
        query_prefix: str = "",
        passage_prefix: str = "",
    ):
        """
        Args:
            model_name: HuggingFace model ID or local path.
            normalize: L2-normalize embeddings (recommended for cosine similarity).
            batch_size: Sentences per GPU/CPU batch.
            query_prefix: Prefix for query texts (e.g. "query: " for E5 models).
            passage_prefix: Prefix for document texts (e.g. "passage: " for E5 models).
        """
        self.model_name = model_name
        self.normalize = normalize
        self.batch_size = batch_size
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self._dim: int = 0

        self._model = self._load_model()

    def _load_model(self):
        """Load SentenceTransformer model onto GPU (fp16) if available, else CPU with ONNX backend."""
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError:
            raise ImportError("sentence-transformers is not installed. " "Run: pip install sentence-transformers")

        if hardware.gpu_count > 0:
            # GPU path: PyTorch fp16 — halves VRAM usage and doubles inference speed.
            model = SentenceTransformer(self.model_name, device="cuda")
            model = model.half()
            logger.info(
                "Embedding model loaded: model=%s device=cuda fp16=True dim=%d",
                self.model_name,
                model.get_embedding_dimension(),
            )
        else:
            # CPU path: try ONNX backend first (2-3x faster than PyTorch fp32),
            # fall back to standard PyTorch if ONNX weights unavailable.
            try:
                model = SentenceTransformer(self.model_name, backend="onnx")
                logger.info(
                    "Embedding model loaded: model=%s device=cpu backend=onnx dim=%d",
                    self.model_name,
                    model.get_embedding_dimension(),
                )
            except Exception:
                model = SentenceTransformer(self.model_name, device="cpu")
                logger.info(
                    "Embedding model loaded: model=%s device=cpu backend=pytorch dim=%d",
                    self.model_name,
                    model.get_embedding_dimension(),
                )

        self._dim = model.get_embedding_dimension()
        return model

    # ------------------------------------------------------------------
    # BaseEmbedding interface
    # ------------------------------------------------------------------

    def get_dimension(self) -> int:
        return self._dim

    def embed(self, text: str, normalize: bool = True) -> list[float]:
        """Embed a single text string."""
        text_with_prefix = self.query_prefix + text if self.query_prefix else text
        vectors = self._model.encode(
            [text_with_prefix],
            normalize_embeddings=normalize and self.normalize,
            batch_size=1,
            show_progress_bar=False,
        )
        return vectors[0].tolist()

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> list[list[float]]:
        """
        Embed multiple texts using the local model.

        Note: SentenceTransformer handles batching internally and uses
        GPU parallelism natively — no ThreadPoolExecutor needed here.
        The `passage_prefix` is applied to document texts during ingestion.
        """
        if not texts:
            return []

        actual_batch = batch_size or self.batch_size

        if self.passage_prefix:
            texts = [self.passage_prefix + t for t in texts]

        vectors = self._model.encode(
            texts,
            normalize_embeddings=normalize and self.normalize,
            batch_size=actual_batch,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        """
        Embed a query text (applies query_prefix if configured).
        Use this for retrieval queries instead of embed() when using E5-style models.
        """
        prefixed = self.query_prefix + text if self.query_prefix else text
        vectors = self._model.encode(
            [prefixed],
            normalize_embeddings=self.normalize,
            batch_size=1,
            show_progress_bar=False,
        )
        return vectors[0].tolist()

    def unload(self) -> None:
        """
        Free GPU/CPU memory used by the model.

        Call this at the end of an ingestion task to release VRAM back to the
        system — letting the vLLM chat model use the full GPU budget.
        The model will be re-loaded from disk cache on the next task.
        """
        try:
            if self._model is not None:
                del self._model
                self._model = None  # type: ignore[assignment]
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logger.info("Embedding model unloaded — CUDA cache cleared")
                else:
                    logger.info("Embedding model unloaded — RAM freed")
            except ImportError:
                logger.info("Embedding model unloaded")
        except Exception:
            logger.warning("Failed to cleanly unload embedding model", exc_info=True)
