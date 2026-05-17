import logging
from typing import Any
from app.modules.documents.repositories import DocumentRepository, SectionRepository

logger = logging.getLogger(__name__)


class TreeService:
    """Service dedicated to document hierarchy and tree visualization."""

    def __init__(self, doc_repo: DocumentRepository, section_repo: SectionRepository):
        self.doc_repo = doc_repo
        self.section_repo = section_repo

    async def get_document_tree(self, document_id: str, offset: int = 0, limit: int = 100) -> dict[str, Any]:
        """
        Fetch sections and return them in a flat list for the table view, paginated.
        """
        # 1. Fetch document for metadata
        doc = await self.doc_repo.get_full_document(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # 2. Fetch paginated sections
        sections, total = await self.section_repo.get_sections_by_document_paginated(
            document_id, offset=offset, limit=limit
        )

        # 3. Map to Frontend TreeNode format
        nodes = []
        for s in sections:
            node = {
                "node_id": s["section_id"],
                "title": s["title"],
                "level": s["level"],
                "breadcrumb": " > ".join(s.get("breadcrumb", [])),
                "parent_id": s.get("parent_section_id"),
                "child_count": 0,
                "text_length": len(s.get("content") or ""),
                "page_number": s.get("page_range") or 1,
                "page_range": s.get("page_range"),
            }
            nodes.append(node)

        return {
            "document_id": document_id,
            "document_title": doc["title"],
            "total_nodes": total,
            "max_depth": 0,  # Depth info not needed for flat list
            "nodes": nodes,
        }

    async def get_node_details(self, document_id: str, node_id: str) -> dict[str, Any]:
        """Fetch full details for a specific section node matching NodeDetail."""
        s = await self.section_repo.get_section_by_section_id(document_id, node_id)
        if not s:
            raise ValueError(f"Node {node_id} not found in document {document_id}")

        return {
            "node_id": s["section_id"],
            "title": s["title"],
            "level": s["level"],
            "breadcrumb": " > ".join(s.get("breadcrumb", [])),
            "text": s.get("content") or "",
            "metadata": {
                "page_number": s.get("page_range") or 1,
                "page_range": s.get("page_range"),
                "node_type": s.get("section_type", "section"),
                "order": s.get("order_index", 0),
                "char_count": len(s.get("content") or ""),
                "token_count": len(s.get("content") or "") // 4,  # Rough estimate if not stored
            },
        }

    async def search_nodes(self, document_id: str, query: str) -> dict[str, Any]:
        """Search for nodes and return in TreeSearchResult format."""
        results = await self.section_repo.search_sections_by_document(document_id, query)

        mapped_results = []
        for r in results:
            content = r.get("content") or ""
            mapped_results.append(
                {
                    "node_id": r["section_id"],
                    "title": r["title"],
                    "preview": content[:200] + "..." if len(content) > 200 else content,
                    "highlight": r["title"],  # Simple highlight for now
                }
            )

        return {"results": mapped_results}
