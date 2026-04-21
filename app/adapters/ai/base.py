from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Generate a chat response."""
        raise NotImplementedError

    async def chat_stream(self, messages: list[dict[str, Any]], **kwargs: Any):
        """
        Stream chat response chunks. Default implementation yields full response.

        Override this method in subclasses for true streaming support.
        """
        response = await self.chat(messages, **kwargs)
        yield response.get("answer", "")

    async def refine_text(self, text: str, current_header: str | None = None, **kwargs: Any) -> tuple[str, str | None]:
        """
        Refine text content (e.g., fix OCR errors, improve readability).
        Returns tuple of (cleaned_text, detected_header).

        Default implementation returns text unchanged.
        """
        return text, current_header

    def _build_context_blocks(
        self,
        context_nodes: list[dict[str, Any]],
        max_context_chars: int = 500000,
    ) -> list[str]:
        """Pack context blocks without a fixed per-node truncation.

        The budget is applied across the whole context so long sections stay intact
        as much as possible while keeping prompts bounded.
        """
        blocks: list[str] = []
        remaining = max(0, int(max_context_chars))

        for idx, node in enumerate(context_nodes, start=1):
            if remaining <= 0:
                break

            title = str(node.get("document_title") or "Untitled")
            heading = str(node.get("heading") or "Section")
            page_range = node.get("page_range") or node.get("metadata", {}).get("page_range")
            full_text = str(node.get("full_text") or node.get("text") or "")

            header = f"[{idx}] {title} | {heading}"
            if page_range:
                header += f" | pages {page_range}"

            if full_text:
                block = f"{header}\n{full_text}"
            else:
                block = header

            if len(block) > remaining:
                available_for_text = max(0, remaining - len(header) - 1)
                if available_for_text <= 0:
                    break
                block = f"{header}\n{full_text[:available_for_text]}"

            blocks.append(block)
            remaining -= len(block)

        return blocks
