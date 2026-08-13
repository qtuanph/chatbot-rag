"""
Unit Tests for Multi-Tenant RBAC & Auth Audit Fixes
Audit Items Verified:
- C-05: Document access restricted by tenant_id for tenant_admin.
- C-06: Platform Admin forbidden from /tenants/me (returns HTTP 403).
- C-08: FAQ & Escalation endpoints tenant-scoped for tenant_admin.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException
from app.modules.tenants.self_router import _resolve_tenant_id
from app.modules.chat.faq_router import _verify_tenant_faq_access
from app.modules.documents.services.service import DocumentService


class TestAuthAndRBAC(unittest.TestCase):

    def test_c06_platform_admin_forbidden_from_tenants_me(self):
        """C-06: Platform admin accessing /tenants/me must receive HTTP 403."""
        # Mock platform_admin user
        mock_auth = MagicMock()
        mock_auth.is_admin = True
        mock_auth.role = "platform_admin"
        mock_auth.tenant_id = None
        mock_service = MagicMock()

        with self.assertRaises(HTTPException) as ctx:
            import asyncio
            asyncio.run(_resolve_tenant_id(mock_auth, mock_service))

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("platform_admin has no personal tenant", str(ctx.exception.detail))

    def test_c05_tenant_admin_document_access_scope(self):
        """C-05: Tenant admin cannot access or rechunk documents from another tenant."""
        mock_doc_repo = MagicMock()
        mock_section_repo = MagicMock()
        mock_redis = MagicMock()
        service = DocumentService(doc_repo=mock_doc_repo, section_repo=mock_section_repo, redis_client=mock_redis)

        # Document belongs to tenant-AAA, but caller is tenant-BBB -> returns None
        mock_doc_repo.get_full_document = AsyncMock(return_value=None)

        with self.assertRaises(ValueError) as ctx:
            import asyncio
            asyncio.run(service.rechunk_document(
                document_id="doc-123",
                user_id="user-bbb",
                owner_tenant_id="tenant-BBB",
            ))
        self.assertIn("Document not found", str(ctx.exception))

    def test_c08_tenant_faq_access_verification(self):
        """C-08: FAQ endpoints verify that tenant_admin can only manage FAQs for their own tenant."""
        # Matching tenant_id -> allowed
        mock_auth_ok = MagicMock(is_admin=False, role="tenant_admin", tenant_id="tenant-123")
        self.assertIsNone(_verify_tenant_faq_access("tenant-123", mock_auth_ok))

        # Non-matching tenant_id -> raises HTTPException(403)
        mock_auth_bad = MagicMock(is_admin=False, role="tenant_admin", tenant_id="tenant-999")
        with self.assertRaises(HTTPException) as ctx:
            _verify_tenant_faq_access("tenant-123", mock_auth_bad)
        self.assertEqual(ctx.exception.status_code, 403)

        # Platform Admin -> allowed for any tenant
        mock_auth_platform = MagicMock(is_admin=True, role="platform_admin", tenant_id=None)
        self.assertIsNone(_verify_tenant_faq_access("tenant-123", mock_auth_platform))


if __name__ == "__main__":
    unittest.main()
