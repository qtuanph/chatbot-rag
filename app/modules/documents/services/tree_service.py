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
        Fetch flat sections and transform them into a hierarchical tree structure matching TreeResponse.
        """
        # 1. Fetch document for metadata
        doc = await self.doc_repo.get_full_document(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # 2. Fetch all sections
        sections = await self.section_repo.get_sections_by_document(document_id)
        if not sections:
            return {
                "document_id": document_id,
                "document_title": doc["title"],
                "total_nodes": 0,
                "max_depth": 0,
                "nodes": [],
            }

        # 3. Build the tree with mapping to Frontend TreeNode format
        lookup = {}
        max_depth = 0

        for s in sections:
            node = {
                "node_id": s["section_id"],
                "title": s["title"],
                "level": s["level"],
                "breadcrumb": " > ".join(s.get("breadcrumb", [])),
                "parent_id": s.get("parent_section_id"),
                "child_count": 0,  # Calculated later if needed, or use a placeholder
                "text_length": len(s.get("content") or ""),
                "page_number": s.get("page_range") or 1,
                "page_range": s.get("page_range"),
                "children": [],
            }
            lookup[s["section_id"]] = node
            max_depth = max(max_depth, s["level"])

        tree = []
        for node_id, node in lookup.items():
            parent_id = node["parent_id"]
            if not parent_id:
                tree.append(node)
            else:
                parent = lookup.get(parent_id)
                if parent:
                    parent["children"].append(node)
                    parent["child_count"] += 1
                else:
                    tree.append(node)

        # 4. Apply pagination to root nodes
        end = offset + limit
        paginated_nodes = tree[offset:end]

        return {
            "document_id": document_id,
            "document_title": doc["title"],
            "total_nodes": len(sections),
            "max_depth": max_depth,
            "nodes": paginated_nodes,
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
