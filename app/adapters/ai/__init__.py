from app.adapters.ai.google import GoogleAIProvider
from app.adapters.ai.local import LocalAIProvider
from app.adapters.ai.vllm import VLLMAIProvider
from app.core.config import settings


def build_ai_provider():
	provider = settings.ai_provider.strip().lower()
	if provider == "google":
		return GoogleAIProvider()
	if provider == "vllm":
		return VLLMAIProvider()
	return LocalAIProvider()


__all__ = ["LocalAIProvider", "GoogleAIProvider", "VLLMAIProvider", "build_ai_provider"]
