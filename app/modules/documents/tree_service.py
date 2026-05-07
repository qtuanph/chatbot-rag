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

    async def get_document_tree(self, document_id: str) -> list[dict[str, Any]]:
        """
        Fetch flat sections and transform them into a hierarchical tree structure.
        """
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

        return tree
