import logging
import mimetypes
from app.core.config import settings

logger = logging.getLogger(__name__)


class DocumentValidator:
    """Utilities for validating document uploads."""

    @staticmethod
    def validate_filename(filename: str | None) -> str:
        """Validate filename for security and length."""
        if not filename:
            raise ValueError("Filename is required")

        if len(filename) > settings.max_filename_length:
            raise ValueError(f"Filename exceeds maximum length of {settings.max_filename_length} characters")

        if "/" in filename or "\\" in filename or ".." in filename or "\x00" in filename:
            raise ValueError("Filename contains invalid path characters")

        return filename

    @staticmethod
    def validate_file_type(content_type: str | None, filename: str | None = None) -> str:
        """Validate file content type with fallback extension checking."""
        file_type = content_type or "application/octet-stream"
        allowed_types = settings.get_allowed_file_types()

        if file_type not in allowed_types:
            # Fall back to guessing MIME type from filename extension
            if filename:
                guessed_type, _ = mimetypes.guess_type(filename)
                if guessed_type and guessed_type in allowed_types:
                    return guessed_type

            raise ValueError(
                f"File type '{file_type}' is not allowed. Allowed types: {', '.join(sorted(allowed_types))}"
            )
        return file_type

    @staticmethod
    def validate_size(size: int) -> None:
        """Validate file size against limits."""
        max_size = settings.max_upload_size_mb * 1024 * 1024
        if size > max_size:
            raise RuntimeError(f"File size exceeds maximum of {settings.max_upload_size_mb} MB")
        if size == 0:
            raise ValueError("File cannot be empty")
