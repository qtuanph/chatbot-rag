"""Document parsers: LlamaParse (cloud OCR) + local markdown parser."""

from app.adapters.parsers.llamaparse_adapter import LlamaParseParser
from app.adapters.parsers.docling import DoclingParser

__all__ = ["LlamaParseParser", "DoclingParser"]
