from __future__ import annotations

from typing import Any

import httpx

from app.adapters.ai.base import AIProvider
from app.core.config import settings


class VLLMAIProvider(AIProvider):
    def __init__(self) -> None:
        self.base_url = settings.vllm_base_url.rstrip("/")
        self.model = settings.vllm_model   # Bug fix: was hardcoded "local-model"

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        payload_messages = self._build_messages(messages, kwargs)
        payload = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        content = ""
        if choices:
            content = (choices[0].get("message") or {}).get("content") or ""

        return {
            "answer": content.strip() or "Không thể tạo câu trả lời từ vLLM ở thời điểm này.",
            "citations": kwargs.get("citations") or [],
        }

    async def refine_text(self, text: str, current_header: str | None = None, **kwargs: Any) -> tuple[str, str | None]:
        """vLLM does not support text refinement by default."""
        return text, current_header

    def _build_messages(self, messages: list[dict[str, Any]], kwargs: dict[str, Any]) -> list[dict[str, str]]:
        context_nodes = kwargs.get("context") or []
        context_lines: list[str] = []
        for idx, node in enumerate(context_nodes, start=1):
            title = node.get("document_title") or "Untitled"
            heading = node.get("heading") or "Section"
            text = (node.get("full_text") or "")[:2000]
            context_lines.append(f"[{idx}] {title} | {heading}\n{text}")

        system_prompt = (
            "You are an enterprise assistant. Answer strictly from provided document context. "
            "If context is insufficient, explicitly say so.\n\n"
            f"Context:\n{chr(10).join(context_lines) if context_lines else 'No document context available.'}"
        )

        formatted: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for message in messages[-12:]:
            role = str(message.get("role", "user"))
            if role not in {"system", "user", "assistant"}:
                role = "user"
            formatted.append({"role": role, "content": str(message.get("content", ""))})
        return formatted
