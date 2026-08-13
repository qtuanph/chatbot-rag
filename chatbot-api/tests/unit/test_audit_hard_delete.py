"""
Unit Tests for Hard-Delete Order & Soft Delete Consistency (H-12, M-05, C-04)
Verifies:
- H-12: CleanupService executes strict 6-step hard-delete sequence.
- C-04: Document sections in PostgreSQL are deleted BEFORE the documents table row.
- M-05: DocumentRepository.soft_delete sets both status='deleted' and status_stage='deleted'.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from app.modules.documents.services.cleanup_service import CleanupService


class TestHardDeleteWorkflow(unittest.TestCase):

    def test_h12_strict_six_step_hard_delete_order(self):
        """H-12: Verify that hard delete follows the exact 6-step lifecycle sequence."""
        mock_doc_repo = MagicMock()
        mock_section_repo = MagicMock()
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = ["task:doc:doc-999"]

        cleanup_service = CleanupService(
            doc_repo=mock_doc_repo,
            section_repo=mock_section_repo,
            redis_client=mock_redis,
        )

        call_order = []

        def step1_redis_hset(*args, **kwargs):
            call_order.append("step1_redis_mark_deleted")

        async def step2_vector_delete(*args, **kwargs):
            call_order.append("step2_vector_delete")

        async def step3_section_delete(*args, **kwargs):
            call_order.append("step3_section_delete")

        def step4_storage_delete(*args, **kwargs):
            call_order.append("step4_storage_delete")

        async def step5_doc_hard_delete(*args, **kwargs):
            call_order.append("step5_doc_hard_delete")

        def step6_redis_delete(*args, **kwargs):
            call_order.append("step6_redis_purge")

        mock_redis.hset.side_effect = step1_redis_hset
        mock_section_repo.delete_sections.side_effect = step3_section_delete
        mock_doc_repo.hard_delete.side_effect = step5_doc_hard_delete
        mock_redis.delete.side_effect = step6_redis_delete

        with patch("app.modules.documents.services.cleanup_service.delete_document_vectors", side_effect=step2_vector_delete), \
             patch("app.modules.documents.services.cleanup_service.build_storage") as mock_build_storage:

            mock_storage_instance = MagicMock()
            mock_storage_instance.delete_prefix.side_effect = step4_storage_delete
            mock_build_storage.return_value = mock_storage_instance

            import asyncio
            asyncio.run(cleanup_service.hard_delete_document("doc-999"))

        expected_sequence = [
            "step1_redis_mark_deleted",
            "step2_vector_delete",
            "step3_section_delete",
            "step4_storage_delete",
            "step5_doc_hard_delete",
            "step6_redis_purge",
        ]

        self.assertEqual(call_order, expected_sequence, "Hard delete violated the strict 6-step deletion order!")

    def test_m05_soft_delete_updates_both_status_and_status_stage(self):
        """M-05: soft_delete() must set status='deleted' and status_stage='deleted'."""
        from app.modules.documents.repositories.repository import DocumentRepository

        mock_session = MagicMock()
        mock_doc = MagicMock()
        mock_doc.status = "completed"
        mock_doc.status_stage = "indexing"

        mock_session.get = AsyncMock(return_value=mock_doc)
        mock_session.commit = AsyncMock()

        repo = DocumentRepository(session=mock_session)
        import asyncio
        asyncio.run(repo.soft_delete("doc-123"))

        self.assertEqual(mock_doc.status, "deleted")
        self.assertEqual(mock_doc.status_stage, "deleted")
        mock_session.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
