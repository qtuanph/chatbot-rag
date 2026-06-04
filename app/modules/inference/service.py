from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from llama_index.core import Settings
from llama_index.core.base.llms.types import ChatMessage, MessageRole

from app.core.config import settings
from app.modules.chat.retrieval.pipeline import retrieve_context
from app.modules.chat.retrieval.usage_tracker import track_usage
from app.modules.chat.utils.chat_utils import compute_cost
from app.modules.tenants.repository import TenantRepository


@dataclass
class CompletionResult:
    content: str
    citations: list[dict[str, Any]]
    usage: dict[str, Any]
    model: str


def _to_llama_role(role: str) -> MessageRole:
    mapping = {
        "system": MessageRole.SYSTEM,
        "user": MessageRole.USER,
        "assistant": MessageRole.ASSISTANT,
        "tool": MessageRole.TOOL,
    }
    return mapping.get(role.lower(), MessageRole.USER)


class PublicInferenceService:
    def __init__(self, tenant_repo: TenantRepository) -> None:
        self.tenant_repo = tenant_repo

    async def complete(
        self,
        *,
        tenant_id: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        user_query = self._latest_user_query(messages)
        setting = await self._get_tenant_setting(tenant_id)
        context = await retrieve_context(
            [user_query],
            limit=settings.retrieval_rerank_top_k,
            tenant_id=tenant_id,
            user_id=None,
        )
        llm_messages = self._build_messages(messages, setting, context)
        llm = Settings.llm
        previous_temperature = getattr(llm, "temperature", None)
        previous_max_tokens = getattr(llm, "max_tokens", None)
        if temperature is not None:
            llm.temperature = temperature
        if max_tokens is not None:
            llm.max_tokens = max_tokens
        try:
            response = await llm.achat(llm_messages)
        finally:
            if temperature is not None:
                llm.temperature = previous_temperature
            if max_tokens is not None:
                llm.max_tokens = previous_max_tokens
        usage = getattr(response, "additional_kwargs", {}) or {}
        content = ""
        message = getattr(response, "message", None)
        if message is not None and hasattr(message, "content"):
            content = str(message.content or "")
        if not content and hasattr(response, "text"):
            content = str(response.text or "")
        result = CompletionResult(
            content=content.strip(),
            citations=self._build_citations(context),
            usage=self._normalize_usage(usage),
            model=getattr(llm, "model", settings.ai_proxy_default_model or "chatbot-rag"),
        )
        provider = type("UsageProxy", (), {"last_usage": result.usage, "model_name": result.model})()
        track_usage(provider, endpoint="public.chat.completions", tenant_id=tenant_id)
        return result

    async def stream_complete(
        self,
        *,
        tenant_id: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        user_query = self._latest_user_query(messages)
        setting = await self._get_tenant_setting(tenant_id)
        context = await retrieve_context(
            [user_query],
            limit=settings.retrieval_rerank_top_k,
            tenant_id=tenant_id,
            user_id=None,
        )
        llm_messages = self._build_messages(messages, setting, context)
        llm = Settings.llm
        previous_temperature = getattr(llm, "temperature", None)
        previous_max_tokens = getattr(llm, "max_tokens", None)
        if temperature is not None:
            llm.temperature = temperature
        if max_tokens is not None:
            llm.max_tokens = max_tokens

        created = int(time.time())
        model_name = getattr(llm, "model", settings.ai_proxy_default_model or "chatbot-rag")
        completion_id = f"chatcmpl-{created}"
        usage_info: dict[str, Any] = {}
        collected_text = ""
        try:
            response = await llm.astream_chat(llm_messages)
            async for chunk in response:
                delta = chunk.delta if hasattr(chunk, "delta") else str(chunk)
                collected_text += delta
                if hasattr(chunk, "additional_kwargs") and isinstance(chunk.additional_kwargs, dict):
                    usage_info.update(chunk.additional_kwargs)
                payload = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_name,
                    "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(payload)}\n\n"
        finally:
            if temperature is not None:
                llm.temperature = previous_temperature
            if max_tokens is not None:
                llm.max_tokens = previous_max_tokens

        normalized_usage = self._normalize_usage(usage_info)
        provider = type("UsageProxy", (), {"last_usage": normalized_usage, "model_name": model_name})()
        track_usage(provider, endpoint="public.chat.completions", tenant_id=tenant_id)
        final_payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "citations": self._build_citations(context),
            "usage": normalized_usage,
        }
        yield f"data: {json.dumps(final_payload)}\n\n"
        yield "data: [DONE]\n\n"

    async def _get_tenant_setting(self, tenant_id: str) -> dict[str, Any]:
        tenant = await self.tenant_repo.get_tenant(tenant_id)
        if tenant is None:
            raise ValueError("Tenant not found")
        setting = await self.tenant_repo.get_setting(tenant_id)
        if setting is None:
            return {
                "chatbot_display_name": tenant["name"],
                "welcome_message": "Xin chào, tôi có thể hỗ trợ gì cho bạn?",
                "system_instruction": "",
            }
        return setting

    @staticmethod
    def _latest_user_query(messages: list[dict[str, str]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user" and message.get("content", "").strip():
                return message["content"].strip()
        raise ValueError("At least one user message is required")

    def _build_messages(self, messages: list[dict[str, str]], setting: dict[str, Any], context) -> list[ChatMessage]:
        context_blocks = []
        for node in context.nodes:
            title = node.document_title or "Document"
            heading = node.heading or "Relevant section"
            page = f" (page {node.page_range})" if node.page_range else ""
            context_blocks.append(f"{title} - {heading}{page}\n{node.full_text}")

        system_prompt = (
            "Bạn là trợ lý doanh nghiệp hoạt động trong đúng phạm vi tenant hiện tại. "
            "Chỉ được trả lời dựa trên tài liệu của tenant và ngữ cảnh hội thoại được cung cấp. "
            "Nếu thông tin chưa đủ, hãy nói rõ là chưa đủ và không được bịa nội dung."
        )
        tenant_instruction = (setting.get("system_instruction") or "").strip()
        if tenant_instruction:
            system_prompt += f"\n\nInstruction riêng của tenant:\n{tenant_instruction}"
        if context_blocks:
            system_prompt += "\n\nNgữ cảnh truy xuất:\n" + "\n\n".join(context_blocks[:10])

        llm_messages = [ChatMessage(role=MessageRole.SYSTEM, content=system_prompt)]
        recent_messages = messages[-settings.ai_max_history_messages :]
        for message in recent_messages:
            llm_messages.append(
                ChatMessage(role=_to_llama_role(message["role"]), content=message.get("content", "").strip())
            )
        return llm_messages

    @staticmethod
    def _build_citations(context) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for idx, node in enumerate(context.nodes, start=1):
            citations.append(
                {
                    "index": idx,
                    "document_id": node.document_id,
                    "title": node.document_title,
                    "heading": node.heading,
                    "page_range": node.page_range,
                    "node_id": node.node_id,
                }
            )
        return citations

    @staticmethod
    def _normalize_usage(usage: dict[str, Any]) -> dict[str, Any]:
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        result = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        result.update(compute_cost(prompt_tokens, completion_tokens))
        return result
