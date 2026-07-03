from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class EmbeddingCapability(enum.Enum):
    DENSE_ONLY = "dense_only"
    NATIVE_SPARSE = "native_sparse"


@dataclass
class EmbeddingResult:
    dense: list[list[float]]
    sparse: list[dict[int, float] | None] | None
    vector_size: int


class EmbeddingAdapter:
    """OpenAI-compatible embedding adapter with auto-detect for sparse support.

    Probes the model endpoint once at first use to determine if it returns
    native sparse weights alongside dense vectors.  If the model supports
    sparse, those weights are returned in ``EmbeddingResult.sparse``;
    otherwise ``sparse`` is ``None`` (the caller should fall back to BM25).

    Config override (via provider ``config`` JSON)::

        {"sparse": "auto"}       -> probe (default)
        {"sparse": "native"}     -> skip probe, assume native sparse
        {"sparse": "bm25"}       -> skip probe, force BM25 fallback
    """

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        config: dict[str, Any] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.config = config or {}
        self._client = http_client
        self._owned_client = http_client is None
        self._capability: EmbeddingCapability | None = None
        self._vector_size: int = 0

    async def __aenter__(self) -> EmbeddingAdapter:
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._owned_client and self._client is not None:
            await self._client.aclose()

    # -- public ----------------------------------------------------------

    @property
    def capability(self) -> EmbeddingCapability:
        if self._capability is None:
            return EmbeddingCapability.DENSE_ONLY
        return self._capability

    @property
    def supports_native_sparse(self) -> bool:
        return self.capability == EmbeddingCapability.NATIVE_SPARSE

    @property
    def vector_size(self) -> int:
        return self._vector_size

    async def probe(self) -> EmbeddingCapability:
        """Auto-detect sparse capability (idempotent -- cached after first call)."""
        if self._capability is not None:
            return self._capability

        # Config override
        sparse_config = self.config.get("sparse", "auto")
        if sparse_config == "native":
            self._set_capability(EmbeddingCapability.NATIVE_SPARSE)
            return self._capability
        if sparse_config == "bm25":
            self._set_capability(EmbeddingCapability.DENSE_ONLY)
            return self._capability

        # Auto-detect: send a single probe request
        client = self._get_client()
        payload: dict[str, Any] = {"input": "Hello world", "model": self.model}
        try:
            resp = await client.post(
                f"{self.api_base}/embeddings",
                json=payload,
                headers=self._headers(),
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            first = (data.get("data") or [{}])[0]
            has_sparse = "sparse_embedding" in first
            if has_sparse:
                self._set_capability(EmbeddingCapability.NATIVE_SPARSE)
            else:
                self._set_capability(EmbeddingCapability.DENSE_ONLY)
        except Exception as exc:
            logger.warning("Embedding probe failed for %s: %s", self.model, exc)
            self._set_capability(EmbeddingCapability.DENSE_ONLY)

        return self._capability

    async def encode(self, texts: list[str], input_type: str | None = None) -> EmbeddingResult:
        """Embed texts and return dense + optional sparse vectors."""
        cap = await self.probe()
        client = self._get_client()

        payload: dict[str, Any] = {"input": texts, "model": self.model}
        
        actual_input_type = input_type or self.config.get("input_type")
        if not actual_input_type:
            model_lower = self.model.lower()
            if "nemotron" in model_lower:
                actual_input_type = "passage"
            elif "embed-multilingual-v3" in model_lower:
                actual_input_type = "search_document"
                
        if actual_input_type:
            payload["input_type"] = actual_input_type
        try:
            resp = await client.post(
                f"{self.api_base}/embeddings",
                json=payload,
                headers=self._headers(),
                timeout=120.0,
            )
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:
            logger.error("Embedding request failed for %s: %s", self.model, exc)
            raise

        data: list[dict[str, Any]] = sorted(body.get("data", []), key=lambda d: d.get("index", 0))
        dense = [d["embedding"] for d in data]
        vector_size = len(dense[0]) if dense else 0
        if self._vector_size == 0:
            self._vector_size = vector_size

        sparse = None
        if cap == EmbeddingCapability.NATIVE_SPARSE:
            sparse = []
            for d in data:
                sw = d.get("sparse_embedding")
                if isinstance(sw, dict) and sw:
                    sparse.append(sw)
                else:
                    sparse.append(None)
            if not any(s is not None for s in sparse):
                sparse = None

        return EmbeddingResult(dense=dense, sparse=sparse, vector_size=vector_size)

    # -- private ---------------------------------------------------------

    def _set_capability(self, cap: EmbeddingCapability) -> None:
        self._capability = cap
        logger.info("Embedding adapter capability for %s: %s", self.model, cap.value)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
        return self._client

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
