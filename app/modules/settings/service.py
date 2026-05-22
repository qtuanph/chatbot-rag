from app.modules.settings.repository import SettingsRepository
from app.modules.settings.schemas import ProviderCreate, ProviderUpdate


TEMPLATES: list[dict] = [
    # Embedding
    {"service_type": "embedding", "provider_name": "tei", "display_name": "TEI (Local)", "url": "http://ai-embedding:80/v1", "model": "Alibaba-NLP/gte-multilingual-base"},
    {"service_type": "embedding", "provider_name": "openai", "display_name": "OpenAI", "url": "https://api.openai.com/v1", "model": "text-embedding-ada-002"},
    {"service_type": "embedding", "provider_name": "openrouter", "display_name": "OpenRouter", "url": "https://openrouter.ai/api/v1", "model": "openai/text-embedding-3-small"},
    {"service_type": "embedding", "provider_name": "nvidia", "display_name": "NVIDIA NIM", "url": "https://ai.api.nvidia.com/v1", "model": "nvidia/nv-embed-qa-4"},
    {"service_type": "embedding", "provider_name": "gemini", "display_name": "Google Gemini", "url": "https://generativelanguage.googleapis.com/v1", "model": "text-embedding-004"},
    {"service_type": "embedding", "provider_name": "cohere", "display_name": "Cohere", "url": "https://api.cohere.com/v1", "model": "embed-multilingual-v3.0"},
    # Reranker
    {"service_type": "reranker", "provider_name": "tei", "display_name": "TEI (Local)", "url": "http://ai-reranker:80", "model": "Alibaba-NLP/gte-multilingual-reranker-base"},
    {"service_type": "reranker", "provider_name": "nvidia", "display_name": "NVIDIA NIM", "url": "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-vl-1b-v2/reranking", "model": "nvidia/llama-nemotron-rerank-vl-1b-v2"},
    {"service_type": "reranker", "provider_name": "cohere", "display_name": "Cohere", "url": "https://api.cohere.com", "model": "rerank-multilingual-v3.0"},
    # LLM
    {"service_type": "llm", "provider_name": "9router", "display_name": "9Router (Built-in)", "url": "http://ai-proxy:2908/v1", "model": "chatbot-rag"},
]


class SettingsService:
    def __init__(self, repo: SettingsRepository | None = None) -> None:
        self.repo = repo or SettingsRepository()

    # ── Providers ─────────────────────────────────────────────────

    def list_providers(self, service_type: str | None = None) -> list[dict]:
        return self.repo.list_providers(service_type)

    def get_provider(self, provider_id: int) -> dict | None:
        return self.repo.get_provider(provider_id)

    def create_provider(self, data: ProviderCreate) -> dict:
        return self.repo.create_provider(data.model_dump())

    def update_provider(self, provider_id: int, data: ProviderUpdate) -> dict | None:
        clean = {k: v for k, v in data.model_dump().items() if v is not None}
        if not clean:
            return self.repo.get_provider(provider_id)
        return self.repo.update_provider(provider_id, clean)

    def delete_provider(self, provider_id: int) -> bool:
        return self.repo.delete_provider(provider_id)

    def activate_provider(self, provider_id: int) -> dict | None:
        return self.repo.activate_provider(provider_id)

    def get_active_provider(self, service_type: str) -> dict | None:
        return self.repo.get_active_provider(service_type)

    def get_templates(self) -> list[dict]:
        return TEMPLATES

    def create_from_template(self, template_name: str, api_key: str = "") -> dict | None:
        for t in TEMPLATES:
            if t["provider_name"] == template_name:
                return self.repo.create_provider({
                    "service_type": t["service_type"],
                    "provider_name": t["provider_name"],
                    "display_name": t["display_name"],
                    "url": t["url"],
                    "model": t["model"],
                    "api_key": api_key,
                    "priority": 0,
                })
        return None

    # ── API Keys ──────────────────────────────────────────────────

    def list_keys(self, provider_id: int) -> list[dict]:
        return self.repo.list_keys(provider_id)

    def add_key(self, provider_id: int, key_value: str) -> dict:
        return self.repo.create_key(provider_id, key_value)

    def delete_key(self, provider_id: int, key_id: int) -> bool:
        return self.repo.delete_key(provider_id, key_id)

    # ── Testing ───────────────────────────────────────────────────

    async def test_provider(self, provider_id: int) -> dict:
        provider = self.repo.get_provider(provider_id)
        if not provider:
            return {"success": False, "message": "Provider not found"}

        import httpx

        url = provider["url"].rstrip("/")
        model = provider["model"]
        api_key = provider["api_key"] or "no-key"

        try:
            if provider["service_type"] == "embedding":
                test_url = f"{url}/embeddings"
                payload = {"input": "test", "model": model}
            elif provider["service_type"] == "reranker":
                test_url = f"{url}"
                payload = {"query": {"text": "test"}, "passages": [{"text": "hello"}], "model": model}
            else:
                test_url = f"{url}/chat/completions"
                payload = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}

            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(test_url, json=payload, headers=headers)
                if resp.status_code < 500:
                    return {"success": True, "message": "Connection OK"}
                return {"success": False, "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"success": False, "message": str(e)[:200]}
