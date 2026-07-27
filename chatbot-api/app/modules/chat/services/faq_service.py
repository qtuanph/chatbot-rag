"""FAQ Service — business logic for creating, updating, deleting FAQs and syncing Redis."""

from __future__ import annotations

import logging
from typing import Any

from app.modules.chat.cache.faq_cache import compute_query_hash, faq_cache_remove_item, faq_cache_sync_item
from app.modules.chat.repositories.escalation_repository import EscalationRepository
from app.modules.chat.utils.query_normalizer import ALL_DEFAULT_STOPWORDS, normalize_query

logger = logging.getLogger(__name__)


def validate_and_compute_hashes(question: str, variants: list[str]) -> list[str]:
    all_q = [question] + (variants or [])
    hashes: list[str] = []
    for q in all_q:
        normalized = normalize_query(q, stopwords=ALL_DEFAULT_STOPWORDS)
        if not normalized:
            continue
        # Safety rule: ensure variant has at least 2 tokens after stopword removal to prevent overly broad matches
        tokens = normalized.split()
        if len(tokens) < 2 and len(q.strip()) > 3:
            logger.warning("FAQ variant '%s' normalized to very short phrase '%s'", q, normalized)
        q_hash = compute_query_hash(q)
        if q_hash and q_hash not in hashes:
            hashes.append(q_hash)
    return hashes


class FAQService:
    def __init__(self, repo: EscalationRepository, redis_client: Any = None) -> None:
        self.repo = repo
        self.redis = redis_client

    async def list_faqs(self, tenant_id: str) -> list[dict[str, Any]]:
        entries = await self.repo.list_faqs_for_tenant(tenant_id)
        return [self._to_dict(e) for e in entries]

    async def list_open_escalations(self, tenant_id: str) -> list[dict[str, Any]]:
        entries = await self.repo.list_open_escalations_for_tenant(tenant_id)
        return [self._to_dict(e) for e in entries]

    async def create_faq(
        self,
        *,
        tenant_id: str,
        question: str,
        answer: str,
        question_variants: list[str] | None = None,
        citations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        variants = question_variants or []
        hashes = validate_and_compute_hashes(question, variants)

        entry = await self.repo.create(
            tenant_id=tenant_id,
            question=question,
            answer=answer,
            question_variants=variants,
            query_hashes=hashes,
            citations=citations or [],
            status="published_faq",
        )

        payload = self._to_redis_payload(entry)
        if self.redis:
            await faq_cache_sync_item(self.redis, tenant_id, hashes, payload)

        return self._to_dict(entry)

    async def update_faq(
        self,
        faq_id: str,
        *,
        question: str | None = None,
        answer: str | None = None,
        question_variants: list[str] | None = None,
        citations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        existing = await self.repo.get_by_id(faq_id)
        if not existing:
            raise ValueError("FAQ entry not found")

        old_hashes = list(existing.query_hashes or [])
        new_q = question if question is not None else existing.question
        new_vars = question_variants if question_variants is not None else list(existing.question_variants or [])
        new_hashes = validate_and_compute_hashes(new_q, new_vars)

        updated = await self.repo.update_faq(
            faq_id,
            question=question,
            answer=answer,
            question_variants=question_variants,
            query_hashes=new_hashes,
            citations=citations,
        )

        if self.redis and updated:
            tenant_str = str(updated.tenant_id)
            # Remove old hashes no longer present
            to_remove = [h for h in old_hashes if h not in new_hashes]
            if to_remove:
                await faq_cache_remove_item(self.redis, tenant_str, to_remove)
            payload = self._to_redis_payload(updated)
            await faq_cache_sync_item(self.redis, tenant_str, new_hashes, payload)

        return self._to_dict(updated)

    async def delete_faq(self, faq_id: str) -> bool:
        existing = await self.repo.get_by_id(faq_id)
        if not existing:
            return False

        old_hashes = list(existing.query_hashes or [])
        tenant_str = str(existing.tenant_id)

        success = await self.repo.delete(faq_id)
        if success and self.redis and old_hashes:
            await faq_cache_remove_item(self.redis, tenant_str, old_hashes)

        return success

    async def promote_escalation(
        self,
        escalation_id: str,
        *,
        question: str | None = None,
        answer: str,
        question_variants: list[str] | None = None,
        citations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        existing = await self.repo.get_by_id(escalation_id)
        if not existing:
            raise ValueError("Escalation not found")

        target_q = question or existing.question
        variants = question_variants or []
        hashes = validate_and_compute_hashes(target_q, variants)

        promoted = await self.repo.update_faq(
            escalation_id,
            question=target_q,
            answer=answer,
            question_variants=variants,
            query_hashes=hashes,
            citations=citations or existing.citations or [],
            status="published_faq",
        )

        if self.redis and promoted:
            tenant_str = str(promoted.tenant_id)
            payload = self._to_redis_payload(promoted)
            await faq_cache_sync_item(self.redis, tenant_str, hashes, payload)

        return self._to_dict(promoted)

    def _to_dict(self, e: Any) -> dict[str, Any]:
        return {
            "id": str(e.id),
            "tenant_id": str(e.tenant_id),
            "conversation_id": e.conversation_id,
            "question": e.question,
            "answer": e.answer,
            "question_variants": e.question_variants or [],
            "citations": e.citations or [],
            "status": e.status,
            "hit_count": getattr(e, "hit_count", 0),
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "updated_at": e.updated_at.isoformat() if getattr(e, "updated_at", None) else None,
        }

    def _to_redis_payload(self, e: Any) -> dict[str, Any]:
        return {
            "id": str(e.id),
            "content": e.answer,
            "citations": e.citations or [],
            "model": "faq_verified",
            "cached_type": "faq",
        }
