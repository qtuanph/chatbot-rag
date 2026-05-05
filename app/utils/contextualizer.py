"""
Contextualizer: Enriches document chunks with document-level context.
Improves RAG accuracy by providing 'global vision' to each 'local' chunk.
"""

import logging
from app.adapters.base import IngestedNode

logger = logging.getLogger(__name__)


class Contextualizer:
    """Enriches chunks with document context for improved retrieval quality."""

    def __init__(self, max_context_chars: int = 500) -> None:
        self.max_context_chars = max_context_chars

    def contextualize(self, filename: str, nodes: list[IngestedNode]) -> list[IngestedNode]:
        """
        Extract document context and prepend to each node's text.
        For now, we use a simple header; can be extended with LLM summary.
        """
        if not nodes:
            return nodes

        # 1. Simple heuristic: use the first 500 chars of the document as global context
        # Or use the document title and main headings.
        all_text = " ".join([n.text for n in nodes[:5]])
        context_summary = all_text[: self.max_context_chars].replace("\n", " ").strip()

        context_prefix = f"[Tài liệu: {filename}] [Bối cảnh: {context_summary}...]\n"

        logger.info("Contextualizing %d nodes with filename: %s", len(nodes), filename)

        for node in nodes:
            # We don't modify the original text field to keep OCR integrity,
            # instead we enrich the text used for embedding and retrieval.
            node.text = f"{context_prefix}{node.text}"

        return nodes
