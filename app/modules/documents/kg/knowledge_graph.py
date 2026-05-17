"""Knowledge Graph module for complex query support."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """
    Simple Knowledge Graph for RAG enhancement.

    This is a placeholder implementation that can be extended with Neo4j
    or NetworkX for production use.

    Features:
    - Entity extraction from documents
    - Relationship mapping
    - Graph-based query routing
    """

    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}
        self.relationships: list[dict] = []

    async def add_document(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """Add document to knowledge graph."""
        entities = self._extract_entities(text)
        for entity in entities:
            entity_id = f"{doc_id}:{entity['name']}"
            self.entities[entity_id] = {
                "name": entity["name"],
                "type": entity["type"],
                "document_id": doc_id,
                "metadata": metadata or {},
            }

    def _extract_entities(self, text: str) -> list[dict]:
        """Simple entity extraction (placeholder)."""
        import re

        entities = []
        proper_nouns = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        for noun in proper_nouns[:10]:
            entities.append({"name": noun, "type": "ENTITY"})
        return entities

    async def query(self, question: str, top_k: int = 5) -> list[dict]:
        """
        Query knowledge graph for relevant entities/relationships.

        Returns list of relevant context dicts.
        """
        keywords = question.lower().split()
        results = []

        for entity_id, entity in self.entities.items():
            name_lower = entity["name"].lower()
            if any(kw in name_lower for kw in keywords):
                results.append(
                    {
                        "entity": entity["name"],
                        "type": entity["type"],
                        "document_id": entity["document_id"],
                    }
                )
            if len(results) >= top_k:
                break

        return results

    async def get_connected_entities(self, entity_name: str, max_depth: int = 2) -> list[dict]:
        """Get entities connected to the given entity."""
        connected = []
        for rel in self.relationships:
            if rel["source"] == entity_name or rel["target"] == entity_name:
                connected.append(rel)
        return connected[:20]

    async def clear(self) -> None:
        """Clear all entities and relationships."""
        self.entities.clear()
        self.relationships.clear()
        logger.info("Knowledge graph cleared")


kg_instance: KnowledgeGraph | None = None


def get_knowledge_graph() -> KnowledgeGraph:
    """Get singleton KnowledgeGraph instance."""
    global kg_instance
    if kg_instance is None:
        kg_instance = KnowledgeGraph()
    return kg_instance
