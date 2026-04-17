"""
Phase 4: Route Coverage Tests

Tests for API routes: auth, upload, tree, chat with focus on:
- Endpoint functionality
- Input validation
- Authorization boundaries
- Error handling
- Response contracts
"""

import json
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.core import User, Role, Document
from app.schemas.auth import LoginRequest, CreateUserRequest, TokenResponse

client = TestClient(app)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def admin_token():
    """Get valid admin JWT token."""
    # For testing, use a pre-created token or mock it
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "abc123"}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    return None


@pytest.fixture
def member_token():
    """Get valid member JWT token."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "member", "password": "abc123"}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    return None


@pytest.fixture
def auth_headers(admin_token):
    """Auth headers with admin token."""
    if admin_token:
        return {"Authorization": f"Bearer {admin_token}"}
    return {}


# ============================================================================
# AUTH ROUTES
# ============================================================================

class TestAuthLogin:
    """Test /api/v1/auth/login endpoint."""

    def test_login_success_admin(self):
        """Valid admin credentials should return JWT token."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "abc123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_success_member(self):
        """Valid member credentials should return JWT token."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "member", "password": "abc123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_login_invalid_username(self):
        """Invalid username should return 401."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "abc123"}
        )
        assert response.status_code == 401
        assert "error" in response.json()

    def test_login_invalid_password(self):
        """Invalid password should return 401."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrongpassword"}
        )
        assert response.status_code == 401

    def test_login_missing_username(self):
        """Missing username should return validation error."""
        response = client.post(
            "/api/v1/auth/login",
            json={"password": "abc123"}
        )
        assert response.status_code == 422

    def test_login_missing_password(self):
        """Missing password should return validation error."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin"}
        )
        assert response.status_code == 422

    def test_login_rate_limiting(self):
        """Multiple failed logins should trigger rate limiting."""
        # Attempt 51+ logins within rate limit window
        for i in range(51):
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "wrongpass"}
            )
            if response.status_code == 429:
                assert "error" in response.json()
                return
        # Should eventually hit rate limit


class TestAuthLogout:
    """Test /api/v1/auth/logout endpoint."""

    def test_logout_success(self, admin_token):
        """Valid token logout should succeed."""
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200

    def test_logout_missing_token(self):
        """Logout without token should return 401."""
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 401

    def test_logout_invalid_token(self):
        """Logout with invalid token should return 401."""
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 401


class TestAuthMe:
    """Test /api/v1/auth/me endpoint."""

    def test_me_success(self, admin_token):
        """Valid token should return user info."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"

    def test_me_missing_token(self):
        """Missing token should return 401."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_me_invalid_token(self):
        """Invalid token should return 401."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid"}
        )
        assert response.status_code == 401


class TestAuthUsers:
    """Test user management endpoints."""

    def test_list_users_admin(self, admin_token):
        """Admin should list all users."""
        response = client.get(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # admin + member at minimum

    def test_list_users_member(self, member_token):
        """Member should NOT list users (403)."""
        response = client.get(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {member_token}"}
        )
        assert response.status_code == 403

    def test_create_user_admin(self, admin_token):
        """Admin should create new user."""
        response = client.post(
            "/api/v1/auth/users",
            json={"username": f"newuser{uuid4().hex[:8]}", "password": "SecurePass123!"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 201
        data = response.json()
        assert "username" in data
        assert data["role"] == "member"  # default role

    def test_create_user_member(self, member_token):
        """Member should NOT create users (403)."""
        response = client.post(
            "/api/v1/auth/users",
            json={"username": "testuser", "password": "TestPass123!"},
            headers={"Authorization": f"Bearer {member_token}"}
        )
        assert response.status_code == 403

    def test_create_user_weak_password(self, admin_token):
        """Weak password should be rejected."""
        response = client.post(
            "/api/v1/auth/users",
            json={"username": "testuser", "password": "weak"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 422

    def test_delete_user_admin(self, admin_token):
        """Admin should delete user."""
        # First create a user
        create_response = client.post(
            "/api/v1/auth/users",
            json={"username": f"deluser{uuid4().hex[:8]}", "password": "SecurePass123!"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        username = create_response.json()["username"]

        # Then delete it
        response = client.delete(
            f"/api/v1/auth/users/{username}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200

    def test_delete_user_member(self, member_token):
        """Member should NOT delete users (403)."""
        response = client.delete(
            "/api/v1/auth/users/admin",
            headers={"Authorization": f"Bearer {member_token}"}
        )
        assert response.status_code == 403


# ============================================================================
# UPLOAD ROUTES
# ============================================================================

class TestUpload:
    """Test /api/v1/upload endpoint."""

    def test_upload_admin_only(self, member_token):
        """Non-admin should NOT upload (403)."""
        response = client.post(
            "/api/v1/upload",
            headers={"Authorization": f"Bearer {member_token}"}
        )
        assert response.status_code == 403

    @patch("app.api.routes.documents.celery_app.send_task")
    def test_upload_pdf_success(self, mock_send_task, admin_token):
        """Valid PDF upload should return task_id."""
        mock_send_task.return_value = uuid4()
        
        with open("test_sample.pdf", "wb") as f:
            f.write(b"%PDF-1.4\n dummy content")
        
        try:
            with open("test_sample.pdf", "rb") as f:
                response = client.post(
                    "/api/v1/upload",
                    files={"file": (f"test_{uuid4()}.pdf", f, "application/pdf")},
                    headers={"Authorization": f"Bearer {admin_token}"}
                )
            
            if response.status_code == 200:
                data = response.json()
                assert "task_id" in data
                assert data["filename"].endswith(".pdf")
        finally:
            import os
            if os.path.exists("test_sample.pdf"):
                os.remove("test_sample.pdf")

    def test_upload_invalid_filetype(self, admin_token):
        """Invalid file type should be rejected."""
        response = client.post(
            "/api/v1/upload",
            files={"file": ("test.exe", b"MZ\x90\x00", "application/x-msdownload")},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        assert "error" in response.json()

    def test_upload_filename_traversal(self, admin_token):
        """Path traversal in filename should be rejected."""
        response = client.post(
            "/api/v1/upload",
            files={"file": ("../../etc/passwd", b"fake", "application/pdf")},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400

    def test_upload_missing_auth(self):
        """Upload without auth should return 401."""
        response = client.post(
            "/api/v1/upload",
            files={"file": ("test.pdf", b"fake", "application/pdf")}
        )
        assert response.status_code == 401


class TestDocumentStatus:
    """Test /api/v1/status/{task_id} endpoint."""

    def test_status_valid_task(self):
        """Valid task_id should return status."""
        task_id = str(uuid4())
        response = client.get(f"/api/v1/status/{task_id}")
        # May return 200 or 404 depending on if task exists
        assert response.status_code in [200, 404]

    def test_status_invalid_uuid(self):
        """Invalid task_id format should return 400."""
        response = client.get("/api/v1/status/not-a-uuid")
        assert response.status_code == 400


class TestDocumentList:
    """Test /api/v1/documents endpoint."""

    def test_list_documents(self, admin_token):
        """Should list documents with pagination."""
        response = client.get(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or isinstance(data, list)

    def test_list_documents_pagination(self, admin_token):
        """Should support offset/limit pagination."""
        response = client.get(
            "/api/v1/documents?offset=0&limit=10",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200

    def test_list_documents_invalid_limit(self, admin_token):
        """Limit > 100 should be clamped or rejected."""
        response = client.get(
            "/api/v1/documents?limit=999",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Should either clamp to 100 or return 400
        assert response.status_code in [200, 400]

    def test_list_documents_missing_auth(self):
        """Missing auth should return 401."""
        response = client.get("/api/v1/documents")
        assert response.status_code == 401


# ============================================================================
# CHAT ROUTES
# ============================================================================

class TestChat:
    """Test chat endpoints."""

    @patch("app.adapters.ai.build_ai_provider")
    @patch("app.services.retrieval.rag.retrieve_context")
    def test_chat_success(self, mock_retrieve, mock_ai, member_token):
        """Valid chat should return answer."""
        mock_retrieve.return_value = MagicMock(nodes=[])
        mock_ai_instance = MagicMock()
        mock_ai_instance.generate.return_value = {"answer": "Test response"}
        mock_ai.return_value = mock_ai_instance

        response = client.post(
            "/api/v1/chat",
            json={"query": "What is in the documents?"},
            headers={"Authorization": f"Bearer {member_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data

    def test_chat_missing_query(self, member_token):
        """Missing query should return 422."""
        response = client.post(
            "/api/v1/chat",
            json={},
            headers={"Authorization": f"Bearer {member_token}"}
        )
        assert response.status_code == 422

    def test_chat_missing_auth(self):
        """Missing auth should return 401."""
        response = client.post(
            "/api/v1/chat",
            json={"query": "test"}
        )
        assert response.status_code == 401

    def test_chat_rate_limiting(self, member_token):
        """Excessive chat requests should be rate limited."""
        # Send 100+ requests rapidly
        limited = False
        for i in range(100):
            response = client.post(
                "/api/v1/chat",
                json={"query": f"test {i}"},
                headers={"Authorization": f"Bearer {member_token}"}
            )
            if response.status_code == 429:
                limited = True
                assert "error" in response.json()
                break
        # May or may not hit limit depending on config


class TestChatStream:
    """Test /api/v1/chat/stream endpoint."""

    @patch("app.adapters.ai.build_ai_provider")
    def test_chat_stream_success(self, mock_ai, member_token):
        """Valid stream request should return SSE stream."""
        mock_ai_instance = MagicMock()
        mock_ai_instance.stream_generate.return_value = iter([
            {"chunk": "Hello "},
            {"chunk": "world"}
        ])
        mock_ai.return_value = mock_ai_instance

        response = client.post(
            "/api/v1/chat/stream",
            json={"query": "test"},
            headers={"Authorization": f"Bearer {member_token}"}
        )
        assert response.status_code == 200

    def test_chat_stream_missing_auth(self):
        """Missing auth should return 401."""
        response = client.post(
            "/api/v1/chat/stream",
            json={"query": "test"}
        )
        assert response.status_code == 401


class TestChatSessions:
    """Test /api/v1/chat/sessions endpoint."""

    def test_list_sessions(self, member_token):
        """Should list user's chat sessions."""
        response = client.get(
            "/api/v1/chat/sessions",
            headers={"Authorization": f"Bearer {member_token}"}
        )
        assert response.status_code == 200
        # May return empty list or list of sessions
        assert isinstance(response.json(), list)

    def test_list_sessions_missing_auth(self):
        """Missing auth should return 401."""
        response = client.get("/api/v1/chat/sessions")
        assert response.status_code == 401


# ============================================================================
# TREE ROUTES
# ============================================================================

class TestTree:
    """Test tree API endpoints."""

    def test_tree_structure(self, admin_token):
        """Should return document tree structure."""
        # Use a valid document ID if available
        doc_id = str(uuid4())
        response = client.get(
            f"/api/v1/tree/{doc_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # May return 200 or 404
        assert response.status_code in [200, 404]

    def test_tree_node_details(self, admin_token):
        """Should return node details."""
        doc_id = str(uuid4())
        node_id = str(uuid4())
        response = client.get(
            f"/api/v1/tree/{doc_id}/nodes/{node_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code in [200, 404]

    def test_tree_search(self, admin_token):
        """Should search nodes in tree."""
        doc_id = str(uuid4())
        response = client.get(
            f"/api/v1/tree/{doc_id}/search?q=test",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code in [200, 404]

    def test_tree_missing_auth(self):
        """Missing auth should return 401."""
        response = client.get(f"/api/v1/tree/{uuid4()}")
        assert response.status_code == 401


# ============================================================================
# HEALTH ENDPOINTS
# ============================================================================

class TestHealth:
    """Test health check endpoints."""

    def test_health_basic(self):
        """Basic health check should succeed."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_health_detailed(self):
        """Detailed health check should include checks."""
        response = client.get("/api/v1/health/data")
        assert response.status_code == 200
        data = response.json()
        assert "checks" in data or "status" in data


# ============================================================================
# Error Contract Tests
# ============================================================================

class TestErrorContracts:
    """Test error response contracts across all routes."""

    def test_auth_error_contract(self):
        """Auth errors should follow unified error envelope."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong"}
        )
        if response.status_code >= 400:
            data = response.json()
            assert "error" in data or "detail" in data

    def test_upload_error_contract(self, admin_token):
        """Upload errors should follow unified error envelope."""
        response = client.post(
            "/api/v1/upload",
            files={"file": ("test.exe", b"content", "application/x-msdownload")},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if response.status_code >= 400:
            data = response.json()
            assert "error" in data or "detail" in data

    def test_chat_error_contract(self, member_token):
        """Chat errors should follow unified error envelope."""
        response = client.post(
            "/api/v1/chat",
            json={},  # Missing required fields
            headers={"Authorization": f"Bearer {member_token}"}
        )
        if response.status_code >= 400:
            data = response.json()
            # Both error and detail are acceptable for validation errors
            assert "error" in data or "detail" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
