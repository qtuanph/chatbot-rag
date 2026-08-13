"""
Unit Tests for Quota Service, Refund & Cache Fixes (H-02, H-11, L-01, Issue #18)
Verifies:
- H-11: refund_llm_call atomically decrements Redis monthly request counter on LLM error.
- Issue #18: Public API key requests (user_id=None) bypass per-user rate limits.
- L-01: is_unanswered_response accurately detects real denials without false positives on legit content.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock
from app.modules.chat.quota.quota_service import QuotaService
from app.modules.inference.service import is_unanswered_response


class TestQuotaAndCache(unittest.TestCase):

    def test_h11_quota_refund_decrements_redis_counters(self):
        """H-11: refund_llm_call decrements monthly request counter on LLM failure."""
        mock_redis = MagicMock()
        mock_redis.decr = AsyncMock(return_value=4)

        quota_service = QuotaService(redis=mock_redis)

        import asyncio
        asyncio.run(quota_service.refund_llm_call(
            tenant_id="tenant-xyz",
        ))

        # Verify redis.decr was called with tenant monthly request key
        mock_redis.decr.assert_called_once()
        called_key = mock_redis.decr.call_args[0][0]
        self.assertIn("quota:tenant_monthly_requests:tenant-xyz", called_key)

    def test_issue18_public_api_key_bypasses_user_rate_limit(self):
        """Issue #18: When user_id is None (Public API key call), per-user rate limit is skipped."""
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_pipeline.execute = AsyncMock(return_value=[5])  # 5 reqs for tenant

        mock_tenant_repo = MagicMock()
        mock_tenant_repo.get_tenant = AsyncMock(return_value={"rate_limit_rpm": 60})

        quota_service = QuotaService(redis=mock_redis, tenant_repo=mock_tenant_repo)

        import asyncio
        is_ok, msg = asyncio.run(quota_service.check_and_increment_rate(
            tenant_id="tenant-abc",
            user_id=None,  # Public API key
        ))

        self.assertTrue(is_ok)
        self.assertEqual(msg, "ok")

        # Verify pipe.incr was called ONLY ONCE for tenant, and NOT for user
        self.assertEqual(mock_pipeline.incr.call_count, 1)
        called_key = mock_pipeline.incr.call_args[0][0]
        self.assertIn("rate:tenant:tenant-abc", called_key)
        self.assertNotIn("rate:user:", called_key)

    def test_l01_unanswered_response_detection(self):
        """L-01: is_unanswered_response accurately detects standard denial phrases."""
        # Definite denials
        self.assertTrue(is_unanswered_response("chưa đủ căn cứ để trả lời."))
        self.assertTrue(is_unanswered_response("không có thông tin về vấn đề này trong tài liệu."))
        self.assertTrue(is_unanswered_response("rất tiếc, tôi không thể tìm thấy dữ liệu."))

        # Legitimate informative answers (must NOT be marked as unanswered)
        self.assertFalse(is_unanswered_response("SAO có 10 phân hệ nghiệp vụ chính bao gồm...", citations=[{"title": "SAO"}]))
        self.assertFalse(is_unanswered_response("Quy định xử lý chứng từ trùng trong mua bán hàng hóa...", citations=[{"title": "SAO"}]))
        self.assertFalse(is_unanswered_response("Người duyệt tài liệu là ông Trần Duy Tăng - Giám đốc.", citations=[{"title": "SAO"}]))


if __name__ == "__main__":
    unittest.main()
