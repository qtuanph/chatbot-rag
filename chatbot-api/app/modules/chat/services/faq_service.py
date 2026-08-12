"""FAQ Service — business logic for creating, updating, deleting FAQs and syncing Redis."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from app.modules.chat.cache.faq_cache import compute_query_hash, faq_cache_remove_item, faq_cache_sync_item
from app.modules.chat.repositories.escalation_repository import EscalationRepository

logger = logging.getLogger(__name__)


def validate_and_compute_hashes(question: str, variants: list[str]) -> list[str]:
    """Compute all Redis index keys for a FAQ question + its variants.

    Uses dual-hashing to guarantee that short/greeting queries
    ("Hi", "Hello", "Chào") — which are fully removed by the stopword filter —
    still produce a valid, deterministic hash and can be looked up in Redis.

    Dual-hash strategy:
      1. compute_query_hash(q)  → stopword-filtered SHA-256 (may be None for pure stopwords)
      2. raw SHA-256(lowercase+punct-stripped q)  → always produces a hash regardless of stopwords

    Both hashes are stored in Redis so lookups from either path always hit.
    """
    all_q = [question] + (variants or [])
    hashes: list[str] = []
    for q in all_q:
        if not q or not q.strip():
            continue

        # Hash 1: stopword-filtered path (handles multi-word semantic deduplication)
        q_hash = compute_query_hash(q)
        if q_hash and q_hash not in hashes:
            hashes.append(q_hash)

        # Hash 2: raw normalized path (guarantees short/greeting queries are always indexed)
        raw_norm = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", q.strip().lower())).strip()
        if raw_norm:
            raw_hash = hashlib.sha256(raw_norm.encode("utf-8")).hexdigest()
            if raw_hash not in hashes:
                hashes.append(raw_hash)
    return hashes


class FAQService:
    def __init__(self, repo: EscalationRepository, redis_client: Any = None) -> None:
        self.repo = repo
        self.redis = redis_client

    async def list_faqs(self, tenant_id: str) -> list[dict[str, Any]]:
        entries = await self.repo.list_faqs_for_tenant(tenant_id)
        if self.redis and entries:
            # Repair Redis index for legacy FAQ entries whose query_hashes are empty.
            # This happens for FAQs created before the dual-hash fix (e.g. question="Hi"
            # was fully stripped by the stopword filter, leaving query_hashes=[]).
            # Only resyncs entries that need it to avoid unnecessary Redis writes.
            for entry in entries:
                if not entry.query_hashes:
                    hashes = validate_and_compute_hashes(entry.question, entry.question_variants or [])
                    if hashes:
                        payload = self._to_redis_payload(entry)
                        await faq_cache_sync_item(self.redis, tenant_id, hashes, payload)
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
            # Remove old hashes that are no longer part of the updated FAQ
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

        tenant_str = str(existing.tenant_id)

        # Merge DB-stored hashes (from creation time) with freshly computed hashes (from
        # the current dual-hash algorithm). This is necessary because legacy FAQs created
        # before the dual-hash fix have query_hashes=[] in the DB, but list_faqs()
        # auto-resync may have already inserted new hashes into Redis. Without this merge,
        # those Redis keys would become stale after deletion.
        old_db_hashes = list(existing.query_hashes or [])
        recomputed_hashes = validate_and_compute_hashes(existing.question, existing.question_variants or [])
        all_hashes_to_remove = list(set(old_db_hashes + recomputed_hashes))

        success = await self.repo.delete(faq_id)
        if success and self.redis and all_hashes_to_remove:
            await faq_cache_remove_item(self.redis, tenant_str, all_hashes_to_remove)

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
