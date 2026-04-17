"""Document management services."""

from app.services.documents.cleanup import hard_delete_document
from app.services.documents.registry import DocumentRecord, DocumentRegistry

__all__ = [
    "hard_delete_document",
    "DocumentRecord",
    "DocumentRegistry",
]
