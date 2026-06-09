from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.modules.chat.repositories.feedback_repository import FeedbackRepository
from app.modules.settings.runtime_manager import RuntimeProviderManager


class FeedbackService:
    def __init__(self, repo: FeedbackRepository) -> None:
        self.repo = repo

    async def submit_feedback(
        self,
        *,
        tenant_id: str,
        user_id: str | None,
        feedback_type: str,
        query_text: str,
        assistant_answer: str,
        citations: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        runtime = RuntimeProviderManager.get_instance()
        embedding_cfg = runtime.get_embedding_config() or {}
        reranker_cfg = runtime.get_reranker_config() or {}
        llm_cfg = runtime.get_llm_config() or {}

        document_ids = []
        section_ids = []
        for citation in citations:
            document_id = str(citation.get("document_id") or "").strip()
            section_id = str(citation.get("section_id") or "").strip()
            if document_id and document_id not in document_ids:
                document_ids.append(document_id)
            if section_id and section_id not in section_ids:
                section_ids.append(section_id)

        payload = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "feedback_type": feedback_type,
            "query_text": query_text.strip(),
            "assistant_answer": assistant_answer.strip(),
            "llm_model": str(llm_cfg.get("model") or settings.ai_proxy_default_model or "chatbot-rag"),
            "embedding_model": str(embedding_cfg.get("model") or settings.embedding_hf_model),
            "reranker_model": str(
                reranker_cfg.get("model")
                or (settings.nvidia_reranker_model if settings.reranker_backend == "nvidia" else settings.ai_reranker_url)
            ),
            "document_ids": document_ids,
            "section_ids": section_ids,
            "citations": citations,
            "metadata": metadata or {},
        }
        return await self.repo.create_feedback(payload)
