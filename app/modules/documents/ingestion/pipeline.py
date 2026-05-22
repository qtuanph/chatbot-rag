"""LlamaIndex-based ingestion pipeline — split, embed, and index with Qdrant native BM25."""

from __future__ import annotations

import logging
from typing import Any

from llama_index.core import Document, Settings as LlamaSettings
from llama_index.core.ingestion import IngestionPipeline as LiIngestionPipeline
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.vector_stores.qdrant import QdrantVectorStore

from app.core.config import settings
from app.core.llama_index import get_vector_store

logger = logging.getLogger(__name__)


def _ingested_nodes_to_llama_docs(
    nodes: list[Any],
    document_id: str,
    sections_data: list[dict[str, Any]] | None = None,
) -> list[Document]:
    """Convert parsed IngestedNodes into LlamaIndex Documents with metadata."""
    section_map = {s["section_id"]: s for s in (sections_data or [])}

    docs = []
    for node in nodes:
        meta = {
            "node_id": node.node_id,
            "document_id": document_id,
            "page_number": node.page_number,
            "section_title": node.section_title,
            "parent_id": node.parent_id,
            "order": node.order,
            **node.metadata,
        }

        sec_id = node.metadata.get("section_id")
        if sec_id and sec_id in section_map:
            sec = section_map[sec_id]
            # Removed: section_content, breadcrumb, level — keep metadata lean

        docs.append(Document(text=node.text, metadata=meta))

    return docs


def build_pipeline() -> LiIngestionPipeline:
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
    )


async def run_ingestion_pipeline(
    nodes: list[Any],
    document_id: str,
    sections_data: list[dict[str, Any]] | None = None,
) -> int:
    """Run the full ingestion pipeline: convert → split → embed → store.

    Uses IngestionPipeline.arun() with vector_store to auto-index.
    Returns the number of stored nodes.
    """
    docs = _ingested_nodes_to_llama_docs(nodes, document_id, sections_data)
    if not docs:
        logger.warning("[%s] No documents to index", document_id)
        return 0

    pipeline = build_pipeline()
    vector_store: QdrantVectorStore = get_vector_store()

    stored_nodes = await pipeline.arun(documents=docs, vector_store=vector_store)
    logger.info(
        "[%s] Pipeline: %d docs → %d nodes stored in Qdrant",
        document_id,
        len(docs),
        len(stored_nodes),
    )

    return len(stored_nodes)
