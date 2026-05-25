"""LlamaIndex-based ingestion pipeline — split, embed, and index with Qdrant native BM25."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from llama_index.core import Document, Settings as LlamaSettings
from llama_index.core.ingestion import IngestionPipeline as LiIngestionPipeline
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import settings
from app.core.llama_index import get_vector_store

logger = logging.getLogger(__name__)

PipelineProgressCallback = Callable[[int, int, int], Awaitable[None] | None]


def _ingested_nodes_to_llama_docs(
    nodes: list[Any],
    document_id: str,
    sections_data: list[dict[str, Any]] | None = None,
) -> list[Document]:
    """Convert parsed IngestedNodes into LlamaIndex Documents with metadata."""
    section_map = {s["section_id"]: s for s in (sections_data or [])}

    docs = []
    for node in nodes:
        # Keep only compact scalar metadata. Large nested fields can break
        # SentenceSplitter with "metadata length > chunk size".
        meta: dict[str, Any] = {
            "node_id": node.node_id,
            "document_id": document_id,
            "page_number": node.page_number,
            "section_title": node.section_title,
            "parent_id": node.parent_id,
            "order": node.order,
        }

        node_meta = node.metadata or {}
        sec_id = node_meta.get("section_id")
        if sec_id and sec_id in section_map:
            sec = section_map[sec_id]
            breadcrumb = sec.get("breadcrumb") or node_meta.get("breadcrumb") or []
            document_title = breadcrumb[0] if isinstance(breadcrumb, list) and breadcrumb else ""
            meta.update(
                {
                    "section_level": sec.get("level", node_meta.get("section_level")),
                    "order_index": sec.get("order_index", node.order),
                    "document_title": document_title,
                    "section_id": sec_id,
                }
            )
        else:
            breadcrumb = node_meta.get("breadcrumb") or []
            document_title = breadcrumb[0] if isinstance(breadcrumb, list) and breadcrumb else ""
            if document_title:
                meta["document_title"] = document_title
            if sec_id:
                meta["section_id"] = sec_id

        # Improve lexical/BM25 recall for heading-based queries (e.g., "mục 2.1", "mục 3")
        # by ensuring section title is included in indexed text.
        text_for_index = node.text
        if node.section_title and node.section_title not in (node.text or ""):
            text_for_index = f"{node.section_title}\n{node.text}"

        # Important: force LlamaIndex ref_doc_id/doc_id to match our real document UUID.
        # If omitted, LlamaIndex generates random IDs per source Document, causing
        # Qdrant payload doc_id/ref_doc_id to drift from PostgreSQL document.id.
        docs.append(Document(id_=document_id, text=text_for_index, metadata=meta))

    return docs


def build_pipeline(vector_store: QdrantVectorStore) -> LiIngestionPipeline:
    """Build a LlamaIndex ingestion pipeline.

    Handles the full flow: heading-based node parsing → sentence splitting
    → embedding via Settings.embed_model → indexing into QdrantVectorStore.
    """
    from app.core.llama_index import init_llama_index

    init_llama_index()

    return LiIngestionPipeline(
        transformations=[
            MarkdownNodeParser(),
            SentenceSplitter(
                chunk_size=settings.ingestion_chunk_size,
                chunk_overlap=settings.ingestion_chunk_overlap,
            ),
            LlamaSettings.embed_model,
        ],
        vector_store=vector_store,
    )


async def run_ingestion_pipeline(
    nodes: list[Any],
    document_id: str,
    sections_data: list[dict[str, Any]] | None = None,
    progress_callback: PipelineProgressCallback | None = None,
) -> int:
    """Run the full ingestion pipeline: convert → split → embed → store.

    Uses IngestionPipeline.arun() with vector_store to auto-index.
    Returns the number of stored nodes.
    """
    docs = _ingested_nodes_to_llama_docs(nodes, document_id, sections_data)
    if not docs:
        logger.warning("[%s] No documents to index", document_id)
        return 0

    vector_store: QdrantVectorStore = get_vector_store()
    pipeline = build_pipeline(vector_store=vector_store)
    # Process one source document node at a time to prevent burst fan-out of chunk embeddings.
    # Actual embedding micro-batch size is still controlled by settings.embedding_batch_size.
    batch_size = 1
    total_stored = 0
    write_observed = False

    async def _ensure_collection() -> None:
        if vector_store._aclient is None:
            return
        exists = await vector_store._aclient.collection_exists(collection_name=vector_store.collection_name)
        if exists:
            return
        await vector_store._aclient.create_collection(
            collection_name=vector_store.collection_name,
            vectors_config={
                vector_store.dense_vector_name: rest.VectorParams(
                    size=settings.embedding_vector_size,
                    distance=rest.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                vector_store.sparse_vector_name: rest.SparseVectorParams(),
            },
        )
        logger.warning("[%s] Auto-created missing Qdrant collection '%s' during ingestion.", document_id, vector_store.collection_name)

    async def _count_points() -> int:
        if vector_store._aclient is None:
            return -1
        try:
            res = await vector_store._aclient.count(
                collection_name=vector_store.collection_name,
                exact=True,
            )
        except UnexpectedResponse as e:
            if "doesn't exist" in str(e):
                await _ensure_collection()
                res = await vector_store._aclient.count(
                    collection_name=vector_store.collection_name,
                    exact=True,
                )
            else:
                raise
        return int(res.count if res is not None else 0)

    await _ensure_collection()

    for start in range(0, len(docs), batch_size):
        batch = docs[start : start + batch_size]
        before_count = await _count_points()
        stored_nodes = await pipeline.arun(
            documents=batch,
            num_workers=1,
        )
        after_count = await _count_points()
        if before_count >= 0 and after_count >= 0 and after_count > before_count:
            write_observed = True
        total_stored += len(stored_nodes)
        processed_docs = min(start + batch_size, len(docs))
        if progress_callback:
            try:
                maybe_awaitable = progress_callback(processed_docs, len(docs), total_stored)
                if maybe_awaitable is not None:
                    await maybe_awaitable
            except Exception:
                logger.warning("[%s] Failed to publish ingestion progress callback", document_id, exc_info=True)
        logger.info(
            "[%s] Pipeline batch %d-%d/%d: %d nodes stored",
            document_id,
            start + 1,
            min(start + batch_size, len(docs)),
            len(docs),
            len(stored_nodes),
        )

    logger.info("[%s] Pipeline complete: %d docs -> %d nodes stored in Qdrant", document_id, len(docs), total_stored)
    if total_stored > 0 and not write_observed:
        raise RuntimeError(
            f"[{document_id}] Embedding pipeline completed but no vectors were persisted to Qdrant. "
            "Check vector_store wiring and Qdrant write path."
        )
    return total_stored
