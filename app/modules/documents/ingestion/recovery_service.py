"""Pipeline recovery service — handles stuck tasks, orphaned data, and consistency checks."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from app.adapters.storage import build_storage
from app.core.llama_index import get_vector_store

if TYPE_CHECKING:
    from app.modules.documents.repositories import DocumentRepository, SectionRepository

logger = logging.getLogger(__name__)
from app.utils.datetime_utils import utc_now


class RecoveryService:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        section_repo: SectionRepository,
        redis_client: Any | None = None,
    ) -> None:
        self.doc_repo = doc_repo
        self.section_repo = section_repo
        self.redis = redis_client
        self.vector_store = get_vector_store()
        self.storage = build_storage()

    async def check_stuck_processing(self, timeout_minutes: int = 30) -> list[str]:
        stuck = await self._find_stuck_documents(timeout_minutes)
        if stuck:
            logger.warning(
                "Found %d documents stuck in processing (timeout=%dm): %s", len(stuck), timeout_minutes, stuck
            )
        return stuck

    async def recover_stuck_document(self, document_id: str, mark_failed: bool = True) -> dict:
        report = {
            "document_id": document_id,
            "actions": [],
            "vectors_found": 0,
            "sections_found": 0,
            "promoted_to_ready": False,
            "marked_failed": False,
        }

        doc = await self.doc_repo.get_full_document(document_id)
        if doc is None:
            report["actions"].append("document_not_found")
            return report

        if doc["status"] != "processing":
            report["actions"].append(f"not_in_processing_state (status={doc['status']})")
            return report

        try:
            from qdrant_client import QdrantClient
            from app.core.config import settings

            def _get_vector_count():
                client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
                res = client.count(
                    collection_name=settings.qdrant_collection,
                    count_filter={"must": [{"key": "document_id", "match": {"value": document_id}}]},
                )
                return res.count if res else 0

            vector_count = await asyncio.to_thread(_get_vector_count)
        except Exception:
            vector_count = 0

        try:
            await self.vector_store.adelete(ref_doc_id=document_id)
        except Exception as e:
            logger.warning("[%s] Failed to delete vectors in recovery: %s", document_id, e)

        report["vectors_found"] = vector_count
        section_count = await self.section_repo.count_by_document(document_id)
        report["sections_found"] = section_count

        if vector_count > 0 or section_count > 0:
            if not mark_failed:
                await self.doc_repo.update_status(
                    document_id,
                    status="ready",
                    stage="ready",
                    progress_percent=100,
                    status_message="Recovered from partial processing.",
                )
                report["promoted_to_ready"] = True
                report["actions"].append(f"promoted_to_ready (vectors={vector_count})")
            else:
                await self.doc_repo.update_status(
                    document_id,
                    status="failed",
                    stage="failed",
                    progress_percent=100,
                    status_message="Stuck in processing, marked as failed for retry.",
                )
                report["marked_failed"] = True
                report["actions"].append("marked_failed")
        else:
            await self.doc_repo.update_status(
                document_id,
                status="failed",
                stage="failed",
                progress_percent=100,
                status_message="Stuck in processing with no data. Marked failed.",
            )
            report["marked_failed"] = True
            report["actions"].append("marked_failed_no_data")

        return report

    async def check_orphaned_vectors(self, document_id: str) -> list[str]:
        orphaned = []
        try:
            section_ids = await self.section_repo.get_section_ids_by_document(document_id)
            from qdrant_client import QdrantClient
            from app.core.config import settings

            def _scroll_sync():
                client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
                points, _ = client.scroll(
                    collection_name=settings.qdrant_collection,
                    scroll_filter={"must": [{"key": "document_id", "match": {"value": document_id}}]},
                    with_payload=True,
                    with_vector=False,
                    limit=10000,
                )
                return points

            def _extract_section_id(payload: dict) -> str | None:
                import json

                sec_id = payload.get("section_id")
                if sec_id is not None:
                    return str(sec_id)
                sec_id = (payload.get("metadata") or {}).get("section_id")
                if sec_id is not None:
                    return str(sec_id)
                raw_node = payload.get("_node_content")
                if isinstance(raw_node, str) and raw_node:
                    try:
                        parsed = json.loads(raw_node)
                        return str((parsed.get("metadata") or {}).get("section_id") or "")
                    except Exception:
                        pass
                return None

            points = await asyncio.to_thread(_scroll_sync)
            for point in points:
                payload = point.payload or {}
                sec_id = _extract_section_id(payload)
                if sec_id and str(sec_id) not in section_ids:
                    orphaned.append(point.id)
        except Exception as e:
            logger.error("[%s] Failed to check orphaned vectors: %s", document_id, e)

        return orphaned

    async def cleanup_orphaned_vectors(self, document_id: str) -> dict:
        report = {"document_id": document_id, "orphaned_count": 0, "cleaned": 0, "error": None}
        try:
            orphaned = await self.check_orphaned_vectors(document_id)
            report["orphaned_count"] = len(orphaned)
            if orphaned:
                from qdrant_client import QdrantClient
                from app.core.config import settings
                from qdrant_client.http import models

                def _delete_sync():
                    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
                    client.delete(
                        collection_name=settings.qdrant_collection,
                        points_selector=models.PointIdsList(points=orphaned),
                    )

                await asyncio.to_thread(_delete_sync)
                report["cleaned"] = len(orphaned)
        except Exception as e:
            report["error"] = str(e)

        return report

    async def validate_section_vector_consistency(self, document_id: str) -> dict:
        report = {"document_id": document_id, "total_vectors": 0, "total_sections": 0, "consistent": True, "issues": []}
        try:
            from qdrant_client import QdrantClient
            from app.core.config import settings

            def _count_sync():
                client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
                result = client.count(
                    collection_name=settings.qdrant_collection,
                    count_filter={"must": [{"key": "document_id", "match": {"value": document_id}}]},
                )
                return result.count if result else 0

            report["total_vectors"] = await asyncio.to_thread(_count_sync)
            section_count = await self.section_repo.count_by_document(document_id)
            report["total_sections"] = section_count

            orphaned = await self.check_orphaned_vectors(document_id)
            if orphaned:
                report["consistent"] = False
                report["issues"].append(f"orphaned_vectors: {len(orphaned)}")
            if section_count > 0 and report["total_vectors"] == 0:
                report["consistent"] = False
                report["issues"].append("sections_exist_but_no_vectors")
        except Exception as e:
            report["consistent"] = False
            report["issues"].append(f"validation_error: {str(e)}")

        return report

    async def idempotency_check(self, task_id: str) -> dict | None:
        if self.redis:
            try:
                doc_id = await self.redis.get(f"task:doc:{task_id}")
                if doc_id:
                    return {"already_processed": True, "task_id": task_id, "document_id": doc_id}
            except Exception:
                pass
        return None

    async def _find_stuck_documents(self, timeout_minutes: int = 30) -> list[str]:
        timeout_threshold = utc_now() - timedelta(minutes=timeout_minutes)
        return await self.doc_repo.find_stuck_documents(timeout_threshold)
