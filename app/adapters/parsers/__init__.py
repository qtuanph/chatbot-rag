"""Document parsers: Docling (primary) + Classic (secondary for unsupported formats)."""

from app.adapters.parsers.docling import DoclingParser
from app.adapters.parsers.classic import ClassicParser

__all__ = ["DoclingParser", "ClassicParser"]
