"""
Memory Extraction Worker: Process chat history to extract user insights.
Uses Sync-Primary architecture for reliable state management.
"""

from __future__ import annotations

import asyncio
import logging
from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.core.redis import get_sync_redis_client

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.memory_tasks.extract_memories_task",
    acks_late=True,
    ignore_result=True,
)
def extract_memories_task(user_id: str, user_message: str, assistant_response: str) -> None:
    """Extract memories from a chat turn (Sync-Primary)."""
    # 1. Sync Infrastructure (For Registry/Metadata if needed)
    sync_redis = get_sync_redis_client()

    async def _run_extraction():
        from app.modules.chat.services import UserMemoryService
        from app.modules.chat.repositories import MemoryRepository
        from app.adapters.ai import build_ai_provider

        # Isolated Async context for AI & DB
        async with AsyncSessionLocal() as session:
            memory_repo = MemoryRepository(session)
            # Use the sync redis client which is safe in this thread
            service = UserMemoryService(redis_client=sync_redis, memory_repo=memory_repo)
            ai_provider = build_ai_provider()

            logger.info("Extracting memories for user %s from chat turn", user_id)
            await service.extract_memories_from_turn(
                user_id=user_id,
                user_message=user_message,
                assistant_response=assistant_response,
                ai_provider=ai_provider,
            )

    try:
        # Standard isolated run
        asyncio.run(_run_extraction())
    except Exception as e:
        logger.error("Memory extraction failed for user %s: %s", user_id, e)
