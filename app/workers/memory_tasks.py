"""Celery task for async memory extraction — more durable than asyncio.create_task."""

import logging
import asyncio
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.memory_tasks.extract_memories_task",
    acks_late=True,
    ignore_result=True,
    max_retries=1,
)
def extract_memories_task(
    user_id: str,
    user_message: str,
    assistant_response: str,
) -> None:
    """Extract user memories from a conversation turn. Fire-and-forget, best-effort."""
    try:
        import redis.asyncio as aioredis
        from app.adapters.ai import build_ai_provider
        from app.core.config import settings
        from app.services.chat.user_memory_service import UserMemoryService

        from app.db.session import SessionLocal
        from app.repositories.memory_repository import MemoryRepository

        # Use async redis client inside asyncio.run
        async def _run_extraction():
            redis_client = aioredis.Redis.from_url(settings.redis_url, decode_responses=True)
            provider = build_ai_provider()
            try:
                with SessionLocal() as session:
                    memory_repo = MemoryRepository(session)
                    service = UserMemoryService(redis_client=redis_client, memory_repo=memory_repo)
                    await service.extract_memories_from_turn(user_id, user_message, assistant_response, provider)
            finally:
                await redis_client.close()

        asyncio.run(_run_extraction())
        
    except Exception as e:
        logger.debug("Memory extraction task failed (best-effort): %s", e)
