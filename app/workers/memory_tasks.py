"""Celery task for async memory extraction — more durable than asyncio.create_task."""

import logging
import asyncio
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.memory_tasks.extract_memories_task",
    bind=True,
    acks_late=True,
    ignore_result=True,
    max_retries=1,
)
def extract_memories_task(
    self,
    user_id: str,
    user_message: str,
    assistant_response: str,
) -> None:
    """Extract user memories from a conversation turn. Fire-and-forget, best-effort."""

    async def _run_extraction():
        from app.adapters.ai import build_ai_provider
        from app.services.chat.user_memory_service import UserMemoryService
        from app.db.session import AsyncSessionLocal
        from app.repositories.memory_repository import MemoryRepository
        from app.core.redis import redis_client

        async with AsyncSessionLocal() as session:
            try:
                memory_repo = MemoryRepository(session)
                provider = build_ai_provider()
                service = UserMemoryService(redis_client=redis_client, memory_repo=memory_repo)

                await service.extract_memories_from_turn(
                    user_id=user_id,
                    user_message=user_message,
                    assistant_response=assistant_response,
                    ai_provider=provider,
                )
            except Exception as e:
                logger.error("Internal memory extraction error: %s", e)

    try:
        asyncio.run(_run_extraction())
    except Exception as e:
        logger.warning("Memory extraction task failed (best-effort): %s", e)
