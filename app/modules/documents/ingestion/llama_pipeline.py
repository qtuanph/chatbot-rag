"""LlamaIndex IngestionPipeline wrapper — SentenceSplitter only.

Embedding and vector storage are handled separately in _vector_index_step
to avoid double-embedding and to keep the custom BM25 + Qdrant flow intact.
"""

from __future__ import annotations

import logging
from typing import List

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document as LlamaDocument

from app.adapters.base import IngestedNode
from app.core.config import settings

logger = logging.getLogger(__name__)


class LlamaIngestionPipeline:
    """Wrap LlamaIndex IngestionPipeline — SentenceSplitter only.

    The pipeline chunks text using LlamaIndex's SentenceSplitter for consistent
    paragraph-aware splitting. Embedding and storage happen downstream in
    _vector_index_step via the existing custom pipeline.
    """

    def __init__(self):
        chunk_size = settings.retrieval_chunk_size * 3  # chars approximation
        chunk_overlap = settings.retrieval_chunk_overlap * 3

        self.pipeline = IngestionPipeline(
            transformations=[
                SentenceSplitter(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    include_metadata=False,  # Metadata không tính vào chunk_size budget
                    # Production pattern: metadata lưu riêng trong DB, không ảnh hưởng split
                ),
            ],
        )

    async def arun(self, documents: List[LlamaDocument]) -> List[dict]:
        """Run ingestion pipeline and return nodes as dicts."""
        nodes = await self.pipeline.arun(documents=documents)
        logger.info("IngestionPipeline produced %d nodes", len(nodes))
        return [n.to_dict() for n in nodes]

    def convert_ingested_nodes(
        self,
        llama_nodes: List[dict],
        document_id: str,
        source_format: str,
    ) -> list[IngestedNode]:
        """Convert LlamaIndex node dicts to IngestedNode for DB storage."""
        result: list[IngestedNode] = []
        for i, nd in enumerate(llama_nodes):
            metadata = nd.get("metadata") or {}
            result.append(
                IngestedNode(
                    node_id=nd.get("id_", nd.get("node_id", f"node_{i:06d}")),
                    document_id=document_id,
                    text=nd.get("text") or nd.get("content") or "",
                    node_type="paragraph",
                    page_number=metadata.get("page_number"),
                    section_title=metadata.get("section_title"),
                    parent_id=metadata.get("parent_id"),
                    order=i,
                    metadata={
                        "source_format": source_format,
                        **metadata,
                    },
                )
            )
        return result
