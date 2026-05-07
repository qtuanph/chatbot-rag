import logging
from app.core import http_errors
from app.core.config import settings

logger = logging.getLogger(__name__)


class DocumentValidator:
    """Utilities for validating document uploads."""

    @staticmethod
    def validate_filename(filename: str | None) -> str:
        """Validate filename for security and length."""
        if not filename:
            raise http_errors.bad_request("Filename is required")

        if len(filename) > settings.max_filename_length:
            raise http_errors.bad_request(
                f"Filename exceeds maximum length of {settings.max_filename_length} characters"
            )

        if "/" in filename or "\\" in filename or ".." in filename or "\x00" in filename:
            raise http_errors.bad_request("Filename contains invalid path characters")

        return filename

    @staticmethod
    def validate_file_type(content_type: str | None) -> str:
        """Validate file content type."""
        file_type = content_type or "application/octet-stream"
        allowed_types = settings.get_allowed_file_types()
        if file_type not in allowed_types:
            raise http_errors.bad_request(
                f"File type '{file_type}' is not allowed. Allowed types: {', '.join(sorted(allowed_types))}"
            )
        return file_type

    @staticmethod
    def validate_size(size: int) -> None:
        """Validate file size against limits."""
        max_size = settings.max_upload_size_mb * 1024 * 1024
        if size > max_size:
            raise http_errors.payload_too_large(f"File size exceeds maximum of {settings.max_upload_size_mb} MB")
        if size == 0:
            raise http_errors.bad_request("File cannot be empty")
