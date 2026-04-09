"""
BGE-M3 Embedding Adapter: Local BAAI/bge-m3 embeddings via sentence-transformers.
Singleton loader for production efficiency.
Supports Vietnamese + technical English documents.
"""

import logging
from typing import List, Optional
import numpy as np

from app.adapters.base import BaseEmbedding
from app.core.exceptions import EmbeddingException

logger = logging.getLogger(__name__)


class BGEM3Embedding(BaseEmbedding):
    """
    BGE-M3 (BAAI General Embedding - Multilingual, Multi-functionality, Multi-granularity) embeddings.
    Vietnamese + English support, 384-dimensional vectors.
    
    Reference: https://huggingface.co/BAAI/bge-m3
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: str = "auto",
        batch_size: int = 32,
        normalize: bool = True,
        max_length: int = 8192,
    ):
        """
        Initialize BGE-M3 embedding model.
        
        Args:
            model_name: HuggingFace model ID (default: BAAI/bge-m3)
            device: Device to use ("auto", "cuda", "cpu")
            batch_size: Batch size for encoding
            normalize: Whether to normalize embeddings (L2 norm)
            max_length: Maximum token length for inputs
        """
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.normalize = normalize
        self.max_length = max_length
        self.model = None
        self._dimension = 384  # BGE-M3 is 384-dimensional
        
        self._initialize_model()

    def _initialize_model(self) -> None:
        """Lazy-initialize the embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info(f"Loading {self.model_name} model...")
            
            # Auto-detect device
            device = self.device
            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"
            
            logger.info(f"Using device: {device}")
            
            self.model = SentenceTransformer(
                self.model_name,
                device=device,
                trust_remote_code=True,
            )
            
            logger.info(f"✓ Loaded {self.model_name} ({self._dimension}-dim vectors)")
        
        except ImportError as e:
            raise EmbeddingException(
                "sentence-transformers not installed; cannot initialize BGE-M3",
                error_code="EMBEDDING_IMPORT_ERROR",
                details={'model': self.model_name, 'error': str(e)}
            )
        except Exception as e:
            raise EmbeddingException(
                f"Failed to load BGE-M3 model: {str(e)}",
                error_code="EMBEDDING_LOAD_FAILED",
                details={'model': self.model_name, 'error': str(e)}
            )

    def get_dimension(self) -> int:
        """Return embedding dimension (384 for BGE-M3)."""
        return self._dimension

    def embed(
        self,
        text: str,
        normalize: bool = None,
    ) -> List[float]:
        """
        Embed a single text string.
        
        Args:
            text: Text to embed
            normalize: Whether to normalize (L2); defaults to instance setting
        
        Returns:
            List of floats (embedding vector)
        
        Raises:
            EmbeddingException: If embedding fails
        """
        if not self.model:
            raise EmbeddingException(
                "Embedding model not initialized",
                error_code="EMBEDDING_NOT_INITIALIZED"
            )
        
        normalize_flag = normalize if normalize is not None else self.normalize
        
        try:
            # Encode single text
            embeddings = self.model.encode(
                text,
                normalize_embeddings=normalize_flag,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            
            return embeddings.tolist()
        except Exception as e:
            raise EmbeddingException(
                f"Failed to embed text: {str(e)}",
                error_code="EMBEDDING_ENCODE_FAILED",
                details={'text_length': len(text), 'error': str(e)}
            )

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = None,
        normalize: bool = None,
    ) -> List[List[float]]:
        """
        Embed multiple texts efficiently in batches.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing (defaults to instance setting)
            normalize: Whether to normalize (L2); defaults to instance setting
        
        Returns:
            List of embedding vectors
        
        Raises:
            EmbeddingException: If embedding fails
        """
        if not self.model:
            raise EmbeddingException(
                "Embedding model not initialized",
                error_code="EMBEDDING_NOT_INITIALIZED"
            )
        
        batch_size = batch_size or self.batch_size
        normalize_flag = normalize if normalize is not None else self.normalize
        
        try:
            # Encode batch
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=normalize_flag,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            
            # Convert numpy array to list of lists
            return embeddings.tolist()
        except Exception as e:
            raise EmbeddingException(
                f"Failed to embed batch of {len(texts)} texts: {str(e)}",
                error_code="EMBEDDING_BATCH_FAILED",
                details={'batch_size': len(texts), 'error': str(e)}
            )

    def health_check(self) -> bool:
        """Check if model is loaded and functional."""
        if not self.model:
            return False
        
        try:
            # Quick test embedding
            test_embedding = self.embed("test")
            return len(test_embedding) == self._dimension
        except Exception:
            return False
