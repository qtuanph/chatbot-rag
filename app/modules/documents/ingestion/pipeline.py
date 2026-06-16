"""Structured ingestion pipeline for canonical sections + dual Qdrant indexes."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Awaitable, Callable

from llama_index.core import Document as LlamaDocument
from llama_index.core import Settings as LlamaSettings
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.node_parser import HierarchicalNodeParser, SentenceWindowNodeParser
from llama_index.core.postprocessor import MetadataReplacementPostProcessor
from llama_index.core.schema import IndexNode, NodeRelationship, TextNode
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import settings
from app.core.llama_index import (
    delete_document_vectors,
    get_async_qdrant_client,
    get_chunk_vector_store,
    get_payload_indexes,
    get_section_vector_store,
    init_llama_index,
)

logger = logging.getLogger(__name__)

WINDOW_METADATA_KEY = "window"
ORIGINAL_TEXT_METADATA_KEY = "original_text"
SECTION_ROUTE_PREFIX = "section::"
PipelineProgressCallback = Callable[[str, int, int, int], Awaitable[None] | None]


def _section_parent_node_id(document_id: str, section_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"section-parent::{document_id}::{section_id}"))


def _section_index_node_id(document_id: str, section_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"section-index::{document_id}::{section_id}"))


def _section_index_id(section_id: str) -> str:
    return f"{SECTION_ROUTE_PREFIX}{section_id}"


def _chunk_node_id(document_id: str, section_id: str, idx: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"chunk::{document_id}::{section_id}::{idx:05d}"))


def _iter_batches(nodes: list[Any], batch_size: int) -> list[list[Any]]:
    return [nodes[index : index + batch_size] for index in range(0, len(nodes), batch_size)]


def _base_metadata(section: dict[str, Any], document_id: str, tenant_id: str) -> dict[str, Any]:
    breadcrumb = section.get("breadcrumb") or []
    breadcrumb_text = section.get("breadcrumb_text") or " > ".join(breadcrumb)
    document_title = breadcrumb[0] if breadcrumb else section.get("title", "")
    return {
        "tenant_id": tenant_id,
        "document_id": document_id,
        "section_id": section["section_id"],
        "section_code": section.get("section_code"),
        "parent_section_id": section.get("parent_section_id"),
        "document_title": document_title,
        "heading": section.get("title", ""),
        "breadcrumb_text": breadcrumb_text,
        "breadcrumb": breadcrumb,
        "level": int(section.get("level", 1) or 1),
        "order_index": int(section.get("order_index", 0) or 0),
    }


def _parser_metadata(section: dict[str, Any], document_id: str, tenant_id: str) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "document_id": document_id,
        "section_id": section["section_id"],
        "section_code": section.get("section_code"),
        "heading": section.get("title", ""),
        "level": int(section.get("level", 1) or 1),
    }


def _section_display_text(section: dict[str, Any]) -> str:
    breadcrumb_text = section.get("breadcrumb_text") or " > ".join(section.get("breadcrumb") or [])
    code = section.get("section_code")
    code_block = f"Mã mục: {code}\n" if code else ""
    content = str(section.get("content") or "").strip()
    preview = content[:1500] if len(content) > 1500 else content
    return (
        f"Tiêu đề: {section.get('title', '')}\n"
        f"{code_block}"
        f"Đường dẫn: {breadcrumb_text}\n\n"
        f"{preview}"
    ).strip()


def _build_section_index_nodes(
    sections_data: list[dict[str, Any]],
    document_id: str,
    tenant_id: str,
) -> list[IndexNode]:
    section_nodes: list[IndexNode] = []
    for section in sections_data:
        metadata = _base_metadata(section, document_id, tenant_id)
        metadata["node_kind"] = "section"
        section_nodes.append(
            IndexNode(
                id_=_section_index_node_id(document_id, section["section_id"]),
                index_id=_section_index_id(section["section_id"]),
                text=_section_display_text(section),
                metadata=metadata,
            )
        )
    return section_nodes


def _build_chunk_nodes(
    sections_data: list[dict[str, Any]],
    document_id: str,
    tenant_id: str,
) -> tuple[list[TextNode], list[TextNode]]:
    parent_nodes: list[TextNode] = []
    chunk_nodes: list[TextNode] = []
    hierarchical_parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=settings.retrieval_hierarchical_chunk_sizes,
        chunk_overlap=settings.retrieval_chunk_overlap,
        include_prev_next_rel=False,
    )

    for section in sections_data:
        content = str(section.get("content") or "").strip()
        if not content:
            continue

        metadata = _base_metadata(section, document_id, tenant_id)
        parser_metadata = _parser_metadata(section, document_id, tenant_id)
        sentence_parser = SentenceWindowNodeParser.from_defaults(
            window_size=settings.retrieval_sentence_window_size,
            window_metadata_key=WINDOW_METADATA_KEY,
            original_text_metadata_key=ORIGINAL_TEXT_METADATA_KEY,
            include_prev_next_rel=False,
            id_func=lambda idx, doc, section_id=section["section_id"]: _chunk_node_id(
                document_id, section_id, idx
            ),
        )
        document = LlamaDocument(
            id_=document_id,
            text=content,
            metadata=parser_metadata,
        )

        sentence_nodes = sentence_parser.get_nodes_from_documents([document])
        try:
            hierarchical_nodes = hierarchical_parser.get_nodes_from_documents([document])
            hierarchical_leaf_count = sum(1 for node in hierarchical_nodes if not node.child_nodes)
            hierarchy_fallback_used = False
        except RecursionError:
            logger.warning(
                "[%s] Hierarchical chunk parsing hit recursion depth for section %s; "
                "continuing with sentence-window chunks only",
                document_id,
                section["section_id"],
            )
            hierarchical_leaf_count = len(sentence_nodes)
            hierarchy_fallback_used = True

        parent_node = TextNode(
            id_=_section_parent_node_id(document_id, section["section_id"]),
            text=content,
            metadata={**metadata, "node_kind": "section_parent"},
        )

        child_refs = []
        for node in sentence_nodes:
            node.metadata.update(metadata)
            node.metadata["node_kind"] = "chunk"
            node.relationships[NodeRelationship.PARENT] = parent_node.as_related_node_info()
            child_refs.append(node.as_related_node_info())
            chunk_nodes.append(node)

        parent_node.relationships[NodeRelationship.CHILD] = child_refs
        parent_nodes.append(parent_node)

        section["chunk_count"] = len(sentence_nodes)
        artifact_metadata = dict(section.get("artifact_metadata") or {})
        artifact_metadata["chunk_node_ids"] = [node.node_id for node in sentence_nodes]
        artifact_metadata["parent_node_id"] = parent_node.node_id
        artifact_metadata["hierarchical_leaf_count"] = hierarchical_leaf_count
        artifact_metadata["hierarchical_chunk_sizes"] = list(settings.retrieval_hierarchical_chunk_sizes)
        artifact_metadata["hierarchy_fallback_used"] = hierarchy_fallback_used
        section["artifact_metadata"] = artifact_metadata

    return parent_nodes, chunk_nodes


async def _ensure_collection(vector_store: QdrantVectorStore) -> None:
    aclient = get_async_qdrant_client()
    payload_indexes = get_payload_indexes()
    exists = await aclient.collection_exists(collection_name=vector_store.collection_name)
    if exists:
        for payload_index in payload_indexes:
            try:
                await aclient.create_payload_index(
                    collection_name=vector_store.collection_name,
                    field_name=payload_index["field_name"],
                    field_schema=payload_index["field_schema"],
                    wait=True,
                )
            except UnexpectedResponse as exc:
                message = str(exc).lower()
                if "already exists" in message or "duplicate" in message:
                    continue
                raise
        return

    dense_name = vector_store.dense_vector_name
    sparse_name = vector_store.sparse_vector_name
    vectors_config: Any
    if dense_name:
        vectors_config = {
            dense_name: rest.VectorParams(
                size=settings.embedding_vector_size,
                distance=rest.Distance.COSINE,
            )
        }
    else:
        vectors_config = rest.VectorParams(
            size=settings.embedding_vector_size,
            distance=rest.Distance.COSINE,
        )

    sparse_vectors_config = None
    if vector_store.enable_hybrid and sparse_name:
        sparse_vectors_config = {sparse_name: rest.SparseVectorParams()}

    await aclient.create_collection(
        collection_name=vector_store.collection_name,
        vectors_config=vectors_config,
        sparse_vectors_config=sparse_vectors_config,
    )

    for payload_index in payload_indexes:
        try:
            await aclient.create_payload_index(
                collection_name=vector_store.collection_name,
                field_name=payload_index["field_name"],
                field_schema=payload_index["field_schema"],
                wait=True,
            )
        except UnexpectedResponse as exc:
            message = str(exc).lower()
            if "already exists" in message or "duplicate" in message:
                continue
            raise


def _index_nodes_sync(
    *,
    nodes: list[Any],
    vector_store: QdrantVectorStore,
    storage_context: StorageContext,
) -> None:
    VectorStoreIndex(
        nodes=nodes,
        use_async=False,
        store_nodes_override=True,
        embed_model=LlamaSettings.embed_model,
        insert_batch_size=max(settings.embedding_batch_size, 1),
        storage_context=storage_context,
        show_progress=False,
    )


async def run_ingestion_pipeline(
    nodes: list[Any],
    document_id: str,
    tenant_id: str,
    sections_data: list[dict[str, Any]] | None = None,
    progress_callback: PipelineProgressCallback | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    """Run the structured dual-index ingestion pipeline."""
    init_llama_index()
    sections_data = [dict(section) for section in (sections_data or [])]
    if not sections_data:
        logger.warning("[%s] No canonical sections to index", document_id)
        return 0, sections_data

    section_store = get_section_vector_store()
    chunk_store = get_chunk_vector_store()
    await _ensure_collection(section_store)
    await _ensure_collection(chunk_store)
    await delete_document_vectors(document_id)

    section_index_nodes = _build_section_index_nodes(sections_data, document_id, tenant_id)
    parent_nodes, chunk_nodes = _build_chunk_nodes(sections_data, document_id, tenant_id)
    total_nodes = len(section_index_nodes) + len(chunk_nodes)
    insert_batch_size = max(settings.embedding_batch_size, 1)

    if progress_callback:
        maybe_awaitable = progress_callback("prepare", 0, total_nodes, 0)
        if maybe_awaitable is not None:
            await maybe_awaitable

    section_storage = StorageContext.from_defaults(vector_store=section_store)
    stored = 0
    for batch in _iter_batches(section_index_nodes, insert_batch_size):
        await asyncio.to_thread(
            _index_nodes_sync,
            nodes=batch,
            vector_store=section_store,
            storage_context=section_storage,
        )
        stored += len(batch)
        if progress_callback:
            maybe_awaitable = progress_callback("section", stored, total_nodes, stored)
            if maybe_awaitable is not None:
                await maybe_awaitable

    chunk_storage = StorageContext.from_defaults(vector_store=chunk_store)
    chunk_storage.docstore.add_documents(parent_nodes + chunk_nodes, allow_update=True)
    chunk_stored = 0
    for batch in _iter_batches(chunk_nodes, insert_batch_size):
        await asyncio.to_thread(
            _index_nodes_sync,
            nodes=batch,
            vector_store=chunk_store,
            storage_context=chunk_storage,
        )
        chunk_stored += len(batch)
        stored += len(batch)
        if progress_callback:
            maybe_awaitable = progress_callback("chunk", chunk_stored, total_nodes, stored)
            if maybe_awaitable is not None:
                await maybe_awaitable

    logger.info(
        "[%s] Structured ingestion complete: %d section nodes, %d chunk nodes",
        document_id,
        len(section_index_nodes),
        len(chunk_nodes),
    )
    return stored, sections_data


def build_context_postprocessor() -> MetadataReplacementPostProcessor:
    return MetadataReplacementPostProcessor(target_metadata_key=WINDOW_METADATA_KEY)
