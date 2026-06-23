"""Local Docker Model Runner reranker via embedding-based scoring.

DMR does not expose a /rerank endpoint and a cross-encoder model
(ai/qwen3-reranker:0.6B) cannot be driven through /chat/completions
in any reliable way. Instead we use the embedding model already
loaded in DMR (ai/qwen3-embedding:0.6B-F16), embed the query and
each candidate text, and rank by cosine similarity. This is a
semantic bi-encoder reranker — less precise than a cross-encoder
but works with any model that DMR actually serves.
"""

from __future__ import annotations

import logging
import math
import re

import httpx
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle

from app.core.config import settings

logger = logging.getLogger(__name__)

_URL_SUFFIX_RE = re.compile(r"/(engines/v1|engines/llama\.cpp/v1|v1)/?$")
_DEFAULT_EMBEDDING_MODEL = "ai/qwen3-embedding:0.6B-F16"


def _normalize_base(url: str) -> str:
    base = (url or "").strip().rstrip("/")
    return _URL_SUFFIX_RE.sub("", base)


def _embeddings_endpoint(base_url: str) -> str:
    return f"{_normalize_base(base_url)}/engines/v1/embeddings"


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    denom = math.sqrt(norm_a) * math.sqrt(norm_b)
    return dot / denom if denom else 0.0


class LocalRerankerPostprocessor(BaseNodePostprocessor):
    """Rerank via DMR embeddings + cosine similarity."""

    top_k: int = settings.retrieval_rerank_top_k
    base_url: str = settings.ai_reranker_url
    embedding_url: str = settings.ai_embedding_url
    embedding_model: str = _DEFAULT_EMBEDDING_MODEL
    timeout: float = settings.ai_reranker_timeout

    async def _embed(self, client: httpx.AsyncClient, inputs: list[str]) -> list[list[float]]:
        url = _embeddings_endpoint(self.embedding_url)
        resp = await client.post(
            url,
            json={"model": self.embedding_model, "input": inputs},
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", []) if isinstance(data, dict) else []
        return [item.get("embedding", []) for item in items]

    async def _postprocess_nodes(
        self,
        nodes: list[NodeWithScore],
        query_bundle: QueryBundle,
    ) -> list[NodeWithScore]:
        if not nodes:
            return nodes

        texts = [(n.node.text or "") for n in nodes]
        # Replace empty texts with a single space so the embedding API
        # never receives an empty string.
        safe_texts = [t if t.strip() else " " for t in texts]

        retries = 3
        backoff = 2
        query_vec: list[float] = []
        doc_vecs: list[list[float]] = []
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    query_resp, docs_resp = await _post_json_pair(
                        client,
                        self.embedding_url,
                        self.embedding_model,
                        query_bundle.query_str,
                        safe_texts,
                    )
                query_vec = query_resp[0] if query_resp else []
                doc_vecs = docs_resp
                break
            except Exception as exc:
                if attempt == retries - 1:
                    logger.warning(
                        "LocalReranker: embedding request failed after retries: %s",
                        exc,
                    )
                    raise
                import asyncio

                await asyncio.sleep(backoff**attempt)

        if not query_vec or not doc_vecs or len(doc_vecs) != len(nodes):
            logger.warning(
                "LocalReranker: embedding vectors missing or mismatched (q=%d, d=%d, expected %d).",
                len(query_vec),
                len(doc_vecs),
                len(nodes),
            )
            return nodes[: self.top_k]

        scored = [(i, _cosine(query_vec, doc_vecs[i])) for i in range(len(nodes))]
        scored.sort(key=lambda pair: pair[1], reverse=True)

        ranked: list[NodeWithScore] = []
        for idx, score in scored[: self.top_k]:
            nodes[idx].score = float(score)
            ranked.append(nodes[idx])
        return ranked


async def _post_json_pair(
    client: httpx.AsyncClient,
    embedding_url: str,
    embedding_model: str,
    query: str,
    texts: list[str],
) -> tuple[list[list[float]], list[list[float]]]:
    """Embed the query and the documents in parallel and return (query_vecs, doc_vecs)."""
    import asyncio

    url = _embeddings_endpoint(embedding_url)
    payload_query = {"model": embedding_model, "input": query}
    payload_docs = {"model": embedding_model, "input": texts}

    async def _call(payload: dict) -> list[list[float]]:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", []) if isinstance(data, dict) else []
        return [item.get("embedding", []) for item in items]

    return await asyncio.gather(_call(payload_query), _call(payload_docs))
