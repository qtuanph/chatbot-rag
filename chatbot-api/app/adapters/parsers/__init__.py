"""Document parsers: LlamaParse (cloud OCR) + Docling local parser."""

from app.adapters.parsers.llamaparse_adapter import LlamaParseParser
from app.adapters.parsers.docling import DoclingParser


def get_parser() -> LlamaParseParser | DoclingParser:
    """Read the active parser provider from RuntimeProviderManager (SQLite) and instantiate."""
    from app.modules.settings.runtime_manager import RuntimeProviderManager

    runtime = RuntimeProviderManager.get_instance()
    cfg = runtime.get_parser_config()
    if cfg is None:
        runtime.reload()
        cfg = runtime.get_parser_config()

    if cfg and cfg.get("provider_name") == "llamaparse":
        api_key = runtime.get_parser_api_key() or cfg.get("api_key")
        if api_key:
            return LlamaParseParser(api_key=api_key)

    # Default: local Docling parser from SQLite
    return DoclingParser()


__all__ = ["LlamaParseParser", "DoclingParser", "get_parser"]
