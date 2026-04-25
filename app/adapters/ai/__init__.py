from functools import lru_cache

from app.adapters.ai.google import GoogleAIProvider
from app.core.config import settings


@lru_cache(maxsize=1)
def build_ai_provider():
    """Cached singleton — returns the same provider instance every time."""
    provider = settings.ai_provider.strip().lower()
    if provider == "google":
        return GoogleAIProvider()
    raise ValueError(
        f"Unsupported AI provider: '{provider}'. Supported: 'google'. "
        f"Set AI_PROVIDER in .env."
    )


__all__ = ["GoogleAIProvider", "build_ai_provider"]
