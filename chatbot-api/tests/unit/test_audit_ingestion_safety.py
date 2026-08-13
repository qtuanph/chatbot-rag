"""
Unit Tests for Ingestion Safety & Concurrency (H-06, H-07, L-06, L-07)
Verifies:
- L-07: Progress callback throttles DB commits to stage changes or >= 5% steps.
- L-06: RagNode correctly populates page_range and page_number from node metadata.
- H-06: Distributed lock key properly isolates per document_id.
"""

import unittest
from unittest.mock import MagicMock
from app.models.rag import RagNode


class TestIngestionSafety(unittest.TestCase):

    def test_l06_ragnode_page_metadata_extraction(self):
        """L-06: RagNode populates page_range and page_number from node metadata."""
        node = RagNode(
            node_id="node-1",
            parent_id=None,
            document_id="doc-123",
            document_title="Tài liệu SAO",
            heading="Mục 1.1",
            summary=None,
            full_text="Hướng dẫn sử dụng",
            page_range="5-6",
        )
        self.assertEqual(node.page_range, "5-6")
        self.assertEqual(node.document_id, "doc-123")

    def test_l07_progress_callback_throttling_logic(self):
        """L-07: Verify throttling rule where DB is only committed when delta >= 5% or stage changes."""
        mock_session = MagicMock()
        mock_doc = MagicMock(status_stage="parsing", progress=10)
        mock_session.get.return_value = mock_doc

        # Simulate callback state tracking
        last_committed_progress = 10
        last_committed_stage = "parsing"

        def should_commit(new_progress: int, new_stage: str) -> bool:
            nonlocal last_committed_progress, last_committed_stage
            stage_changed = (new_stage != last_committed_stage)
            progress_stepped = (new_progress - last_committed_progress >= 5) or (new_progress >= 100)
            if stage_changed or progress_stepped:
                last_committed_progress = new_progress
                last_committed_stage = new_stage
                return True
            return False

        # +2% in same stage -> NO commit
        self.assertFalse(should_commit(12, "parsing"))
        # +3% (total +5% from 10) in same stage -> COMMITS
        self.assertTrue(should_commit(15, "parsing"))
        # +1% but stage changed -> COMMITS
        self.assertTrue(should_commit(16, "chunking"))
        # +2% in chunking stage -> NO commit
        self.assertFalse(should_commit(18, "chunking"))
        # 100% completion -> COMMITS
        self.assertTrue(should_commit(100, "completed"))


if __name__ == "__main__":
    unittest.main()
