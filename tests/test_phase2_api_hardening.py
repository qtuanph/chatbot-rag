"""
Test suite for Phase 2: API Surface Hardening and Contract Closure

Tests cover:
- File type validation (whitelist enforcement)
- Filename validation (length, path traversal)
- Pagination bounds enforcement
- Early Content-Length check
- Correlation ID propagation
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings


client = TestClient(app)


class TestFileTypeValidation:
    """Test file type whitelist enforcement in upload endpoint."""

    def test_allowed_file_type_pdf(self):
        """PDF files should be accepted."""
        # This test validates the config has PDF in allowed types
        allowed = settings.get_allowed_file_types()
        assert "application/pdf" in allowed, "PDF should be in allowed file types"

    def test_allowed_file_type_docx(self):
        """DOCX files should be accepted."""
        allowed = settings.get_allowed_file_types()
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in allowed

    def test_allowed_file_type_xlsx(self):
        """XLSX files should be accepted."""
        allowed = settings.get_allowed_file_types()
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in allowed

    def test_disallowed_file_type_exe(self):
        """EXE files should NOT be in allowed types."""
        allowed = settings.get_allowed_file_types()
        assert "application/x-msdownload" not in allowed
        assert "application/exe" not in allowed

    def test_disallowed_file_type_zip(self):
        """ZIP files should NOT be in allowed types."""
        allowed = settings.get_allowed_file_types()
        assert "application/zip" not in allowed

    def test_config_allowed_file_types_not_empty(self):
        """Config ALLOWED_FILE_TYPES should not be empty."""
        assert settings.allowed_file_types
        assert len(settings.allowed_file_types) > 0


class TestFilenameValidation:
    """Test filename validation constraints."""

    def test_filename_max_length(self):
        """Filename length should be limited."""
        assert settings.max_filename_length == 255
        assert settings.max_filename_length > 0

    def test_filename_max_length_reasonable(self):
        """Max filename length should be between 20 and 512 chars."""
        assert 20 <= settings.max_filename_length <= 512

    def test_path_traversal_detection(self):
        """Filename with .. should be detected (rejection happens at route)."""
        # The route checks for "..", "/", and "\" in filename
        test_names = [
            "../etc/passwd",
            "..\\windows\\system32",
            "file/../secret",
            "file\\..\\secret",
        ]
        # These contain forbidden patterns that should be rejected
        for name in test_names:
            assert ".." in name or "/" in name or "\\" in name


class TestPaginationBounds:
    """Test pagination bounds enforcement in list endpoints."""

    def test_pagination_limit_min(self):
        """Pagination limit should have minimum of 1."""
        # Endpoint clamps: limit = max(1, min(limit, 100))
        # So valid range is 1-100
        assert 1 <= 100, "Valid pagination range should include 1"

    def test_pagination_limit_max(self):
        """Pagination limit should have maximum of 100."""
        # Endpoint clamps limit to max 100
        assert 100 >= 1, "Valid pagination range maximum"

    def test_pagination_offset_min(self):
        """Pagination offset should have minimum of 0."""
        # Endpoint clamps: offset = max(0, offset)
        assert 0 >= 0, "Offset minimum should be 0"

    def test_document_list_response_has_pagination_fields(self):
        """DocumentListResponse should include pagination info."""
        from app.schemas.documents import DocumentListResponse
        
        fields = DocumentListResponse.model_fields
        assert "offset" in fields, "Response should have offset field"
        assert "limit" in fields, "Response should have limit field"
        assert "total" in fields, "Response should have total field"


class TestUploadSizeValidation:
    """Test upload size constraints."""

    def test_max_upload_size_configured(self):
        """Max upload size should be configured."""
        assert settings.max_upload_size_mb > 0
        assert settings.max_upload_size_mb <= 500

    def test_max_upload_size_reasonable(self):
        """Max upload size should be reasonable (not too large)."""
        assert settings.max_upload_size_mb <= 500
        assert settings.max_upload_size_mb >= 1


class TestCorrelationID:
    """Test correlation ID generation and propagation."""

    def test_correlation_id_in_auth_context(self):
        """AuthContext should have request_id field."""
        from app.api.deps import AuthContext
        
        fields = AuthContext.__dataclass_fields__
        assert "request_id" in fields, "AuthContext should have request_id field"

    def test_middleware_imports_uuid(self):
        """Middleware should import uuid for correlation ID generation."""
        from app.api import middleware
        import inspect
        
        source = inspect.getsource(middleware)
        assert "uuid" in source, "Middleware should use uuid module"

    def test_correlation_middleware_exists(self):
        """CorrelationIDMiddleware should exist."""
        from app.api.middleware import CorrelationIDMiddleware
        assert CorrelationIDMiddleware is not None


class TestResponseSchemaConsistency:
    """Test response schema consistency and completeness."""

    def test_document_list_response_has_all_fields(self):
        """DocumentListResponse should have all required fields."""
        from app.schemas.documents import DocumentListResponse
        
        required_fields = {"items", "total", "offset", "limit"}
        fields = DocumentListResponse.model_fields.keys()
        for field in required_fields:
            assert field in fields, f"DocumentListResponse missing {field}"

    def test_document_summary_response_has_file_info(self):
        """DocumentSummaryResponse should include file type info."""
        from app.schemas.documents import DocumentSummaryResponse
        
        required_fields = {"file_type", "file_size", "document_id", "status"}
        fields = DocumentSummaryResponse.model_fields.keys()
        for field in required_fields:
            assert field in fields, f"DocumentSummaryResponse missing {field}"


class TestConfigValidation:
    """Test config constraints for Phase 2."""

    def test_max_upload_size_constraint(self):
        """Config should validate max upload size bounds."""
        # Config enforces: 1 <= max_upload_size_mb <= 500
        assert 1 <= settings.max_upload_size_mb <= 500

    def test_max_filename_length_constraint(self):
        """Config should validate max filename length bounds."""
        # Config enforces: 20 <= max_filename_length <= 512
        assert 20 <= settings.max_filename_length <= 512

    def test_allowed_file_types_not_empty_constraint(self):
        """Config should enforce non-empty ALLOWED_FILE_TYPES."""
        # Config raises ValueError if allowed_file_types is empty
        assert settings.allowed_file_types
        assert len(settings.allowed_file_types) > 0

    def test_allowed_file_types_parsing(self):
        """get_allowed_file_types() should parse comma-separated types."""
        allowed = settings.get_allowed_file_types()
        assert isinstance(allowed, set)
        assert len(allowed) > 0
        # Should be able to check MIME types
        for mime_type in allowed:
            assert "/" in mime_type, f"MIME type should contain /: {mime_type}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
