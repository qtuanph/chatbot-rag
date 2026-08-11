"""Structured retrieval pipeline: section route + sentence-window chunks + reranker."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

from llama_index.core import QueryBundle, VectorStoreIndex, Settings as LlamaSettings
from llama_index.core import StorageContext
from llama_index.core.postprocessor import LongContextReorder
from llama_index.core.retrievers import AutoMergingRetriever, RecursiveRetriever
from llama_index.core.schema import NodeRelationship, NodeWithScore, RelatedNodeInfo, TextNode
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.vector_stores.types import FilterCondition, MetadataFilter, MetadataFilters, VectorStoreQueryMode

from app.adapters.reranker import get_reranker
from app.core.config import settings
from app.core.llama_index import get_chunk_vector_store, get_section_vector_store
from app.db.session import AsyncSessionLocal
from app.models.rag import RagContext, RagNode
from app.modules.documents.ingestion.pipeline import build_context_postprocessor

logger = logging.getLogger("uvicorn.error")

SECTION_CODE_QUERY_RE = re.compile(r"\b\d+(?:\.\d+)+\b")
SECTION_ROUTE_ROOT_ID = "sections_root"
SECTION_ROUTE_PREFIX = "section::"


def _estimate_tokens_from_chars(text: str) -> int:
    return max(0, len(text or "") // 3)


def _query_terms(query: str) -> list[str]:
    return [term for term in str(query or "").strip().split() if term]


def _should_prioritize_section_route(query: str) -> bool:
    cleaned = str(query or "").strip()
    if not cleaned:
        return False
    if SECTION_CODE_QUERY_RE.search(cleaned):
        return True
    if (
        len(cleaned) <= settings.retrieval_route_section_max_chars
        and len(_query_terms(cleaned)) <= settings.retrieval_route_section_max_terms
    ):
        return True
    return False


def _should_skip_rerank(query: str, nodes: list[NodeWithScore]) -> tuple[bool, str]:
    if not settings.retrieval_rerank_skip_enabled:
        return False, "disabled"
    if not nodes:
        return False, "no-nodes"
    cleaned = str(query or "").strip()
    if len(cleaned) > settings.retrieval_rerank_skip_query_max_chars:
        return False, "long-query"
    if len(_query_terms(cleaned)) > settings.retrieval_rerank_skip_query_max_terms:
        return False, "many-terms"
    if len(nodes) == 1:
        return True, "single-result"

    top1 = float(nodes[0].score or 0.0)
    top2 = float(nodes[1].score or 0.0)
    if top1 <= 0:
        return False, "non-positive-top1"
    if top2 <= 0:
        return True, "top2-missing-or-zero"
    ratio = top1 / max(top2, 1e-9)
    if ratio >= settings.retrieval_rerank_skip_dominance_ratio:
        return True, f"dominant-top1:{ratio:.2f}"
    return False, f"weak-dominance:{ratio:.2f}"


def _dispatch_model_usage(
    *,
    model_name: str,
    model_type: str,
    prompt_tokens: int,
    completion_tokens: int = 0,
    latency_ms: float = 0.0,
    endpoint: str,
    tenant_id: str | None,
    user_id: str | None,
) -> None:
    try:
        from app.modules.chat.tasks.usage_tasks import log_model_usage_task

        log_model_usage_task.delay(
            model_name=model_name or "unknown",
            model_type=model_type,
            prompt_tokens=max(0, int(prompt_tokens)),
            completion_tokens=max(0, int(completion_tokens)),
            endpoint=endpoint,
            latency_ms=max(0.0, float(latency_ms)),
            cost_micros_vnd=0,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    except Exception as exc:
        logger.warning("Failed to dispatch %s usage: %s", model_type, exc)


def _preview_text(text: str, limit: int = 240) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def _serialize_nodes_for_debug(nodes: list[NodeWithScore], limit: int = 5) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for node_with_score in nodes[:limit]:
        metadata = node_with_score.node.metadata or {}
        serialized.append(
            {
                "node_id": node_with_score.node.node_id,
                "score": round(float(node_with_score.score or 0.0), 6),
                "document_id": metadata.get("document_id"),
                "document_title": metadata.get("document_title"),
                "section_id": metadata.get("section_id"),
                "section_code": metadata.get("section_code"),
                "heading": metadata.get("heading"),
                "node_kind": metadata.get("node_kind"),
                "preview": _preview_text(node_with_score.node.get_content()),
            }
        )
    return serialized


def _emit_debug(event: str, **payload: Any) -> None:
    message = json.dumps({"event": event, **payload}, ensure_ascii=False)
    logger.info(message)
    print(message, flush=True)


def _tenant_filters(
    tenant_id: str | None,
    allowed_doc_ids: list[str] | None = None,
    *,
    section_id: str | None = None,
) -> MetadataFilters | None:
    if allowed_doc_ids:
        doc_filters = [MetadataFilter(key="document_id", value=d_id) for d_id in allowed_doc_ids]
        if section_id:
            return MetadataFilters(
                filters=[
                    MetadataFilter(key="section_id", value=section_id),
                    MetadataFilters(filters=doc_filters, condition=FilterCondition.OR),
                ]
            )
        return MetadataFilters(filters=doc_filters, condition=FilterCondition.OR)

    filters: list[MetadataFilter] = []
    if tenant_id:
        filters.append(MetadataFilter(key="tenant_id", value=tenant_id))
    if section_id:
        filters.append(MetadataFilter(key="section_id", value=section_id))
    if not filters:
        return None
    return MetadataFilters(filters=filters)


def _query_mode() -> VectorStoreQueryMode:
    return VectorStoreQueryMode.HYBRID if settings.retrieval_hybrid_enabled else VectorStoreQueryMode.DEFAULT


async def _load_tenant_sections_and_doc_ids(
    tenant_id: str | None,
) -> tuple[list[str], list[dict[str, Any]]]:
    async with AsyncSessionLocal() as session:
        from app.modules.documents.repositories import DocumentAccessRepository, SectionRepository

        access_repo = DocumentAccessRepository(session)
        section_repo = SectionRepository(session)
        doc_ids = []
        if tenant_id:
            doc_ids = await access_repo.get_document_ids_for_tenant(tenant_id)
        if doc_ids:
            sections = await section_repo.get_sections_by_allowed_documents(doc_ids)
        elif tenant_id:
            sections = await section_repo.get_sections_by_tenant(tenant_id)
        else:
            sections = await section_repo.get_all_sections()
        return doc_ids, sections


class SafeKVDocumentStore(SimpleDocumentStore):
    def get_document(self, doc_id: str, raise_error: bool = True) -> Any:
        return super().get_document(doc_id, raise_error=False)


def _build_parent_storage_context(sections: list[dict[str, Any]]) -> StorageContext:
    docstore = SafeKVDocumentStore()
    storage_context = StorageContext.from_defaults(docstore=docstore)
    parent_nodes: list[TextNode] = []

    for section in sections:
        artifact_metadata = dict(section.get("artifact_metadata") or {})
        child_ids = [str(node_id) for node_id in artifact_metadata.get("chunk_node_ids", []) if str(node_id)]
        parent_node_id = (
            artifact_metadata.get("parent_node_id")
            or f"section-parent::{section['document_id']}::{section['section_id']}"
        )
        metadata = {
            "tenant_id": section.get("tenant_id"),
            "document_id": section.get("document_id"),
            "section_id": section.get("section_id"),
            "section_code": section.get("section_code"),
            "parent_section_id": section.get("parent_section_id"),
            "document_title": (section.get("breadcrumb") or [section.get("title")])[0],
            "heading": section.get("title"),
            "breadcrumb_text": section.get("breadcrumb_text"),
            "breadcrumb": section.get("breadcrumb") or [],
            "level": section.get("level"),
            "order_index": section.get("order_index"),
            "node_kind": "section_parent",
        }
        parent_node = TextNode(
            id_=str(parent_node_id),
            text=str(section.get("content") or ""),
            metadata=metadata,
        )
        if child_ids:
            parent_node.relationships[NodeRelationship.CHILD] = [
                RelatedNodeInfo(node_id=node_id) for node_id in child_ids
            ]
        parent_nodes.append(parent_node)
    storage_context.docstore.add_documents(parent_nodes, allow_update=True)
    return storage_context


def _build_chunk_index() -> VectorStoreIndex:
    return VectorStoreIndex.from_vector_store(get_chunk_vector_store())


def _build_section_index() -> VectorStoreIndex:
    return VectorStoreIndex.from_vector_store(get_section_vector_store())


class SafeRecursiveRetriever(RecursiveRetriever):
    """RecursiveRetriever that dynamically creates child retrievers for unmapped section IDs."""

    def __init__(
        self,
        *,
        tenant_id: str | None,
        allowed_doc_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._tenant_id = tenant_id
        self._allowed_doc_ids = allowed_doc_ids

    def _get_object(self, query_id: str) -> Any:
        if query_id in self._retriever_dict:
            return self._retriever_dict[query_id]
        if query_id in self._query_engine_dict:
            return self._query_engine_dict[query_id]

        if query_id.startswith(SECTION_ROUTE_PREFIX):
            sec_id = query_id[len(SECTION_ROUTE_PREFIX) :]
            chunk_index = _build_chunk_index()
            retriever = chunk_index.as_retriever(
                filters=_tenant_filters(self._tenant_id, allowed_doc_ids=self._allowed_doc_ids, section_id=sec_id),
                vector_store_query_mode=_query_mode(),
                similarity_top_k=settings.retrieval_recursive_top_k,
                hybrid_top_k=settings.retrieval_recursive_top_k,
                sparse_top_k=settings.retrieval_recursive_top_k,
            )
            self._retriever_dict[query_id] = retriever
            return retriever

        return self._retriever_dict.get(SECTION_ROUTE_ROOT_ID)


def _build_section_recursive_retriever(
    *,
    tenant_id: str | None,
    allowed_doc_ids: list[str] | None = None,
    sections: list[dict[str, Any]],
) -> SafeRecursiveRetriever:
    section_index = _build_section_index()
    chunk_index = _build_chunk_index()
    common_kwargs = {
        "vector_store_query_mode": _query_mode(),
        "similarity_top_k": settings.retrieval_section_top_k,
        "hybrid_top_k": settings.retrieval_section_top_k,
        "sparse_top_k": settings.retrieval_section_top_k,
    }
    retriever_dict: dict[str, Any] = {
        SECTION_ROUTE_ROOT_ID: section_index.as_retriever(
            filters=_tenant_filters(tenant_id, allowed_doc_ids=allowed_doc_ids),
            **common_kwargs,
        )
    }
    for section in sections:
        retriever_dict[f"{SECTION_ROUTE_PREFIX}{section['section_id']}"] = chunk_index.as_retriever(
            filters=_tenant_filters(tenant_id, allowed_doc_ids=allowed_doc_ids, section_id=str(section["section_id"])),
            vector_store_query_mode=_query_mode(),
            similarity_top_k=settings.retrieval_recursive_top_k,
            hybrid_top_k=settings.retrieval_recursive_top_k,
            sparse_top_k=settings.retrieval_recursive_top_k,
        )
    return SafeRecursiveRetriever(
        root_id=SECTION_ROUTE_ROOT_ID,
        retriever_dict=retriever_dict,
        tenant_id=tenant_id,
        allowed_doc_ids=allowed_doc_ids,
    )


class SafeAutoMergingRetriever(AutoMergingRetriever):
    """AutoMergingRetriever that safely strips un-stored sibling node relationships and preserves leaf chunk details."""

    def _fill_in_nodes(self, nodes: list[NodeWithScore]) -> tuple[list[NodeWithScore], bool]:
        original_leaf_nodes = [n for n in nodes]
        cleaned_nodes: list[NodeWithScore] = []
        for n in nodes:
            node = n.node
            if (
                hasattr(node, "next_node")
                and node.next_node
                and not self._storage_context.docstore.document_exists(node.next_node.node_id)
            ):
                node.relationships.pop(NodeRelationship.NEXT, None)
            if (
                hasattr(node, "prev_node")
                and node.prev_node
                and not self._storage_context.docstore.document_exists(node.prev_node.node_id)
            ):
                node.relationships.pop(NodeRelationship.PREVIOUS, None)
            cleaned_nodes.append(n)
        merged_nodes, is_merged = super()._fill_in_nodes(cleaned_nodes)
        if is_merged:
            return _dedupe_nodes(merged_nodes + original_leaf_nodes), True
        return merged_nodes, False


def _build_auto_merging_retriever(
    *,
    tenant_id: str | None,
    allowed_doc_ids: list[str] | None = None,
    storage_context: StorageContext,
) -> SafeAutoMergingRetriever:
    chunk_index = _build_chunk_index()
    vector_retriever = chunk_index.as_retriever(
        filters=_tenant_filters(tenant_id, allowed_doc_ids=allowed_doc_ids),
        vector_store_query_mode=_query_mode(),
        similarity_top_k=settings.retrieval_chunk_top_k,
        hybrid_top_k=settings.retrieval_chunk_top_k,
        sparse_top_k=settings.retrieval_chunk_top_k,
    )
    return SafeAutoMergingRetriever(
        vector_retriever=vector_retriever,
        storage_context=storage_context,
        simple_ratio_thresh=settings.retrieval_auto_merge_ratio_threshold,
        verbose=False,
    )


def _dedupe_nodes(nodes: list[NodeWithScore]) -> list[NodeWithScore]:
    deduped: list[NodeWithScore] = []
    seen: set[str] = set()
    for node in nodes:
        if node.node.node_id in seen:
            continue
        seen.add(node.node.node_id)
        deduped.append(node)
    return deduped


async def retrieve_context(
    queries: list[str],
    session: Any = None,
    limit: int = 20,
    positive_point_ids: list[str] | None = None,
    negative_point_ids: list[str] | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> RagContext:
    del session, positive_point_ids, negative_point_ids

    if not queries:
        return RagContext(nodes=[], sections=None, confidence={"node_count": 0})

    allowed_doc_ids, sections = await _load_tenant_sections_and_doc_ids(tenant_id)
    storage_context = _build_parent_storage_context(sections)
    recursive_retriever = _build_section_recursive_retriever(
        tenant_id=tenant_id, allowed_doc_ids=allowed_doc_ids, sections=sections
    )
    auto_merging_retriever = _build_auto_merging_retriever(
        tenant_id=tenant_id, allowed_doc_ids=allowed_doc_ids, storage_context=storage_context
    )
    replacement_postprocessor = build_context_postprocessor()
    reorder = LongContextReorder() if settings.retrieval_long_context_reorder_enabled else None

    reranker = None
    all_nodes: list[NodeWithScore] = []

    for query in queries:
        qb = QueryBundle(query_str=query)
        query_nodes: list[NodeWithScore] = []

        if not qb.embedding:
            try:
                t0_embed = time.perf_counter()
                embed_model = LlamaSettings.embed_model
                qb.embedding = await embed_model.aget_query_embedding(query)
                embed_latency_ms = (time.perf_counter() - t0_embed) * 1000
                embed_model_name = (
                    getattr(embed_model, "model_name", None)
                    or getattr(embed_model, "base_url", None)
                    or embed_model.__class__.__name__
                )
                embed_prompt_tokens = _estimate_tokens_from_chars(query)
                _dispatch_model_usage(
                    model_name=str(embed_model_name),
                    model_type="embedding",
                    prompt_tokens=embed_prompt_tokens,
                    completion_tokens=0,
                    latency_ms=embed_latency_ms,
                    endpoint="retrieval.embed",
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            except Exception as e:
                logger.warning("Failed to manual embed for usage tracking: %s", e)

        if _should_prioritize_section_route(query):
            t0_section = time.perf_counter()
            section_nodes = await asyncio.to_thread(recursive_retriever.retrieve, qb)
            query_nodes.extend(section_nodes)
            _emit_debug(
                "RAG_SECTION_ROUTE",
                query=query,
                tenant_id=tenant_id,
                latency_ms=round((time.perf_counter() - t0_section) * 1000, 2),
                nodes=_serialize_nodes_for_debug(section_nodes),
            )

        t0_semantic = time.perf_counter()
        semantic_nodes = await asyncio.to_thread(auto_merging_retriever.retrieve, qb)
        query_nodes.extend(semantic_nodes)
        _emit_debug(
            "RAG_SEMANTIC_ROUTE",
            query=query,
            tenant_id=tenant_id,
            latency_ms=round((time.perf_counter() - t0_semantic) * 1000, 2),
            nodes=_serialize_nodes_for_debug(semantic_nodes),
        )

        query_nodes = _dedupe_nodes(query_nodes)
        query_nodes = replacement_postprocessor.postprocess_nodes(query_nodes, qb)
        _emit_debug(
            "RAG_RETRIEVE",
            query=query,
            tenant_id=tenant_id,
            retrieved=len(query_nodes),
            nodes=_serialize_nodes_for_debug(query_nodes),
        )

        skip_rerank, skip_reason = _should_skip_rerank(query, query_nodes)
        if not skip_rerank:
            if reranker is None:
                reranker = get_reranker(top_k=limit)
            if reranker is not None:
                try:
                    t0_rerank = time.perf_counter()
                    reranked_nodes = await reranker.postprocess_nodes(query_nodes, qb)
                    rerank_latency_ms = (time.perf_counter() - t0_rerank) * 1000
                    rerank_model_name = (
                        getattr(reranker, "model_name", None)
                        or getattr(reranker, "base_url", None)
                        or reranker.__class__.__name__
                    )
                    rerank_prompt_tokens = _estimate_tokens_from_chars(query) + _estimate_tokens_from_chars(
                        "".join(node.node.get_content() for node in query_nodes)
                    )
                    _dispatch_model_usage(
                        model_name=str(rerank_model_name),
                        model_type="reranker",
                        prompt_tokens=rerank_prompt_tokens,
                        completion_tokens=0,
                        latency_ms=rerank_latency_ms,
                        endpoint="retrieval.rerank",
                        tenant_id=tenant_id,
                        user_id=user_id,
                    )
                    _emit_debug(
                        "RAG_RERANK",
                        query=query,
                        tenant_id=tenant_id,
                        model=str(rerank_model_name),
                        latency_ms=round(rerank_latency_ms, 2),
                        before=_serialize_nodes_for_debug(query_nodes),
                        after=_serialize_nodes_for_debug(reranked_nodes or []),
                    )
                    if reranked_nodes:
                        query_nodes = reranked_nodes
                except Exception as e:
                    logger.warning("Reranker failed for query='%s': %s; using pre-rerank nodes.", query, str(e))
            else:
                _emit_debug("RAG_RERANK_SKIPPED", query=query, reason="disabled_in_settings")
        else:
            logger.info("Skip reranker for query='%s' (%s).", query, skip_reason)

        if reorder is not None:
            query_nodes = reorder.postprocess_nodes(query_nodes, qb)
            _emit_debug("RAG_REORDER", query=query, tenant_id=tenant_id, nodes=_serialize_nodes_for_debug(query_nodes))

        all_nodes.extend(query_nodes)

    all_nodes = _dedupe_nodes(all_nodes)
    all_nodes.sort(key=lambda node: node.score or 0.0, reverse=True)
    all_nodes = all_nodes[:limit]

    rag_nodes: list[RagNode] = []
    for node_with_score in all_nodes:
        node = node_with_score.node
        metadata = node.metadata or {}
        full_text = node.get_content()
        rag_nodes.append(
            RagNode(
                node_id=node.node_id,
                parent_id=(
                    node.parent_node.node_id if node.parent_node is not None else metadata.get("parent_section_id")
                ),
                document_id=str(metadata.get("document_id") or ""),
                document_title=str(metadata.get("document_title") or ""),
                heading=str(metadata.get("heading") or ""),
                summary=full_text[:400],
                full_text=full_text,
                page_range=None,
                section_id=str(metadata.get("section_id") or "") or None,
                section_code=str(metadata.get("section_code") or "") or None,
                breadcrumb=tuple(metadata.get("breadcrumb") or []),
                node_kind=str(metadata.get("node_kind") or "chunk"),
                score=float(node_with_score.score or 0.0),
            )
        )

    top_score = float(all_nodes[0].score or 0.0) if all_nodes else 0.0
    second_score = float(all_nodes[1].score or 0.0) if len(all_nodes) > 1 else 0.0
    dominance_ratio = top_score / max(second_score, 1e-9) if second_score > 0 else (999.0 if top_score > 0 else 0.0)
    confidence = {
        "node_count": len(rag_nodes),
        "top_score": top_score,
        "second_score": second_score,
        "dominance_ratio": dominance_ratio,
        "unique_document_count": len({node.document_id for node in rag_nodes if node.document_id}),
    }

    _emit_debug(
        "RAG_FINAL",
        tenant_id=tenant_id,
        limit=limit,
        confidence=confidence,
        nodes=[
            {
                "node_id": node.node_id,
                "score": round(float(node.score or 0.0), 6),
                "document_id": node.document_id,
                "document_title": node.document_title,
                "section_id": node.section_id,
                "section_code": node.section_code,
                "heading": node.heading,
                "node_kind": node.node_kind,
                "preview": _preview_text(node.full_text or node.summary or ""),
            }
            for node in rag_nodes[:5]
        ],
    )

    return RagContext(nodes=rag_nodes, sections=None, confidence=confidence)
