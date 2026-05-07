import logging
from typing import Any
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.section_repository import SectionRepository

logger = logging.getLogger(__name__)


class TreeService:
    """Service dedicated to document hierarchy and tree visualization."""

    def __init__(self, doc_repo: DocumentRepository, section_repo: SectionRepository):
        self.doc_repo = doc_repo
        self.section_repo = section_repo

    async def get_document_tree(self, document_id: str, offset: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        """
        Fetch flat sections and transform them into a hierarchical tree structure.
        Supports pagination for large documents (optional, currently fetches all to build tree).
        """
        # Note: To build a proper tree, we usually need all sections.
        # If we paginate at the DB level, the tree structure will be broken.
        # However, we can paginate the root level nodes if needed.

        # 1. Fetch all sections ordered by order_index
        sections = await self.section_repo.get_sections_by_document(document_id)
        if not sections:
            return []

        # 2. Build the tree using a mapping approach
        tree = []
        lookup = {s["section_id"]: {**s, "children": []} for s in sections}

        for sec_id, node in lookup.items():
            parent_id = node.get("parent_section_id")
            if not parent_id:
                # Root level section
                tree.append(node)
            else:
                # Child section: attach to parent if parent exists in lookup
                parent = lookup.get(parent_id)
                if parent:
                    parent["children"].append(node)
                else:
                    # Orphan node or parent is not in this document's scope
                    tree.append(node)

        # 3. Apply pagination to root nodes
        end = offset + limit
        return tree[offset:end]

    async def get_node_details(self, document_id: str, node_id: str) -> dict[str, Any]:
        """Fetch full details for a specific section node."""
        node = await self.section_repo.get_section_by_section_id(document_id, node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found in document {document_id}")
        return node

    async def search_nodes(self, document_id: str, query: str) -> list[dict[str, Any]]:
        """Search for nodes by title or content within a document hierarchy."""
        return await self.section_repo.search_sections_by_document(document_id, query)
