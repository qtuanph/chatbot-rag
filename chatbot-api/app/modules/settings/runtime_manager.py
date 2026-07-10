import threading
from typing import Any

from llama_index.core import Settings

from app.core.config import settings
from app.adapters.embedding.adapter import EmbeddingAdapter


class RuntimeProviderManager:
    """Singleton — overrides LlamaIndex Settings with SQLite-configured providers."""

    _instance: "RuntimeProviderManager | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._embedding: dict[str, Any] | None = None
        self._reranker: dict[str, Any] | None = None
        self._llm: dict[str, Any] | None = None
        self._parser: dict[str, Any] | None = None
        self._key_cursors: dict[int, int] = {}

    @classmethod
    def get_instance(cls) -> "RuntimeProviderManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def init(self) -> None:
        """Load active providers from SQLite on startup."""
        self._load_all()
        self.apply()

    def reload(self) -> None:
        """Re-read from SQLite and re-apply to LlamaIndex Settings."""
        self._key_cursors.clear()
        self._load_all()
        self.apply()

    def _load_all(self) -> None:
        from app.modules.settings.repository import SettingsRepository

        repo = SettingsRepository()
        try:
            self._embedding = repo.get_active_provider("embedding")
            self._reranker = repo.get_active_provider("reranker")
            self._llm = repo.get_active_provider("llm")
            self._parser = repo.get_active_provider("parser")
        finally:
            repo.close()

    def apply(self) -> None:
        """Override Settings.embed_model / Settings.llm from SQLite if available."""
        # Override embedding
        emb = self._embedding
        if emb and emb.get("url"):
            try:
                from app.core.llama_index import SequentialOpenAIEmbedding

                api_key = self._get_effective_key(emb) or "no-key"
                model_name = emb.get("model")
                if not model_name:
                    raise ValueError("Embedding model is missing in SQLite configuration.")
                Settings.embed_model = SequentialOpenAIEmbedding(
                    model_name=model_name,
                    api_base=emb["url"].rstrip("/"),
                    api_key=api_key,
                    embed_batch_size=settings.embedding_batch_size,
                )
            except Exception:
                import logging

                logging.getLogger(__name__).warning("Failed to override embedding provider", exc_info=True)

        # Override LLM from SQLite — 9Router is now managed via SQLite/webapp
        llm = self._llm
        if llm and llm.get("url"):
            try:
                from llama_index.llms.openai_like import OpenAILike

                api_key = self._get_effective_key(llm) or "no-key"
                model_name = llm.get("model")
                if not model_name:
                    raise ValueError("LLM model is missing in SQLite configuration.")
                Settings.llm = OpenAILike(
                    model=model_name,
                    api_base=llm["url"].rstrip("/"),
                    api_key=api_key,
                    is_chat_model=True,
                    is_function_calling_model=True,
                    context_window=128000,
                    temperature=settings.ai_temperature,
                    max_tokens=settings.ai_max_output_tokens,
                    timeout=settings.ai_proxy_timeout,
                )
            except Exception:
                import logging

                logging.getLogger(__name__).warning("Failed to override LLM provider", exc_info=True)

    # ── Public accessors ─────────────────────────────────────────

    def get_embedding_config(self) -> dict[str, Any] | None:
        return self._embedding

    def get_reranker_config(self) -> dict[str, Any] | None:
        return self._reranker

    def get_llm_config(self) -> dict[str, Any] | None:
        return self._llm

    def get_parser_config(self) -> dict[str, Any] | None:
        return self._parser

    def get_parser_api_key(self) -> str | None:
        if not self._parser:
            return None
        return self._get_effective_key(self._parser)

    def get_llm_api_base(self) -> str:
        """9Router base URL (without /v1) for admin/model-listing endpoints."""
        if not self._llm:
            return ""
        url = self._llm.get("url", "")
        for suffix in ("/v1", "v1"):
            if url.endswith(suffix):
                url = url[: -len(suffix)]
                break
        return url.rstrip("/")

    def get_llm_api_key(self) -> str:
        """9Router API key (round-robin aware, else direct field)."""
        if not self._llm:
            return ""
        return self._get_effective_key(self._llm) or self._llm.get("api_key") or ""

    def get_llm_model(self) -> str:
        """Active LLM model name, purely from SQLite."""
        if not self._llm:
            return ""
        return self._llm.get("model") or ""

    # ── Round-robin keys ─────────────────────────────────────────

    def get_embedding_adapter(self) -> EmbeddingAdapter | None:
        """Create an embedding adapter from the active provider."""
        from app.adapters.embedding.factory import get_embedding_adapter as _make_adapter

        if self._embedding:
            return _make_adapter(provider=self._embedding)
        return None

    def get_embedding_api_key(self) -> str | None:
        if not self._embedding:
            return None
        return self._get_effective_key(self._embedding)

    def get_reranker_api_key(self) -> str | None:
        if not self._reranker:
            return None
        return self._get_effective_key(self._reranker)

    def _get_effective_key(self, provider: dict[str, Any]) -> str | None:
        """Get key: round-robin with rate-limit awareness via api_keys table, else use provider.api_key."""
        from app.modules.settings.repository import SettingsRepository

        repo = SettingsRepository()
        try:
            key = repo.get_next_key(provider["id"])
            if key:
                return key
            return provider.get("api_key") or None
        finally:
            repo.close()
