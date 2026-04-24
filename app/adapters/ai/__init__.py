from app.adapters.ai.google import GoogleAIProvider
from app.core.config import settings


def build_ai_provider():
    provider = settings.ai_provider.strip().lower()
    if provider == "google":
        return GoogleAIProvider()
    raise ValueError(
        f"Unsupported AI provider: '{provider}'. Supported: 'google'. "
        f"Set AI_PROVIDER in .env."
    )


__all__ = ["GoogleAIProvider", "build_ai_provider"]
