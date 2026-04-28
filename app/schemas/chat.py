from pydantic import BaseModel, Field, field_validator
import re


class ChatRequest(BaseModel):
    """Request model for chat endpoints with enhanced validation."""

    query: str = Field(min_length=3, max_length=5000, description="User question or query")
    session_id: str | None = Field(default=None, description="Optional session ID to continue existing chat")

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query for security and content."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")

        # Check for dangerous patterns (XSS prevention)
        dangerous_patterns = [
            "<script",
            "javascript:",
            "onerror=",
            "onload=",
            "onfocus=",
            "onblur=",
            "<iframe",
            "<object",
            "<embed",
        ]

        query_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in query_lower:
                raise ValueError("Query contains invalid characters or patterns")

        # Check for excessive special characters (potential abuse)
        special_char_ratio = len(re.findall(r"[^\w\s]", v)) / max(len(v), 1)
        if special_char_ratio > 0.5:
            raise ValueError("Query contains too many special characters")

        return v.strip()

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str | None) -> str | None:
        """Validate session ID format if provided."""
        if v is not None:
            # Basic format check (should be UUID-like)
            if not re.match(r"^[a-f0-9\-]{36}$", v.lower()):
                raise ValueError("Invalid session ID format")
        return v
