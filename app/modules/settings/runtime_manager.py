import threading
from typing import Any

from llama_index.core import Settings

from app.core.config import settings


class RuntimeProviderManager:
    """Singleton — overrides LlamaIndex Settings with SQLite-configured providers."""

    _instance: "RuntimeProviderManager | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._embedding: dict[str, Any] | None = None
        self._reranker: dict[str, Any] | None = None
        self._llm: dict[str, Any] | None = None
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
                model_name = emb.get("model") or settings.embedding_hf_model
                Settings.embed_model = SequentialOpenAIEmbedding(
                    model_name=model_name,
                    api_base=emb["url"].rstrip("/"),
                    api_key=api_key,
                    embed_batch_size=settings.embedding_batch_size,
                )
            except Exception:
                import logging

                logging.getLogger(__name__).warning("Failed to override embedding provider", exc_info=True)

        # Override LLM (if not 9Router built-in or if user added custom)
        llm = self._llm
        if llm and llm.get("url") and not llm.get("is_builtin"):
            try:
                from llama_index.llms.openai_like import OpenAILike

                api_key = self._get_effective_key(llm) or llm.get("api_key") or "no-key"
                Settings.llm = OpenAILike(
                    model=llm.get("model") or settings.ai_proxy_default_model or "default",
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

    # ── Round-robin keys ─────────────────────────────────────────

    def get_embedding_api_key(self) -> str | None:
        if not self._embedding:
            return None
        return self._get_effective_key(self._embedding)

    def get_reranker_api_key(self) -> str | None:
        if not self._reranker:
            return None
        return self._get_effective_key(self._reranker)

    def _get_effective_key(self, provider: dict[str, Any]) -> str | None:
        """Get key: round-robin if multiple api_keys exist, else use provider.api_key."""
        from app.modules.settings.repository import SettingsRepository

        repo = SettingsRepository()
        try:
            keys = repo.list_keys(provider["id"])
            if keys:
                active = [k for k in keys if k["is_active"]]
                if not active:
                    return provider.get("api_key") or None
                pid = provider["id"]
                cursor = self._key_cursors.get(pid, 0)
                idx = cursor % len(active)
                self._key_cursors[pid] = cursor + 1
                return active[idx]["key_value"]
            return provider.get("api_key") or None
        finally:
            repo.close()
