"""
Celery tasks for chat operations — offloaded from API.
Uses Sync-Primary architecture for Redis state updates.
"""

import asyncio
import logging
from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.core.redis import get_sync_redis_client
from app.utils.chat_store import ChatStore

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.chat_tasks.save_chat_message_task",
    acks_late=True,
    ignore_result=True,
)
def save_chat_message_task(**kwargs) -> None:
    """
    Saves a chat message to DB (Async) and Redis (Sync).
    """
    # 1. Sync Redis Update
    try:
        user_id = kwargs.get("user_id")
        session_id = kwargs.get("session_id")
        role = kwargs.get("role")
        content = kwargs.get("content")

        if user_id and session_id:
            sync_redis = get_sync_redis_client()
            chat_store = ChatStore(sync_redis)
            chat_store.append_message_sync(f"user:{user_id}", session_id, role, content)
    except Exception as e:
        logger.warning("Failed to save chat message to Redis: %s", e)

    # 2. Async DB Save (Isolated)
    async def _save_to_db():
        from app.modules.chat.repository import ChatRepository

        async with AsyncSessionLocal() as session:
            repo = ChatRepository(session)
            await repo.create_message(
                session_id=kwargs.get("session_id"),
                role=kwargs.get("role"),
                content=kwargs.get("content"),
                citations=kwargs.get("citations"),
                tokens_in=kwargs.get("tokens_in"),
                tokens_out=kwargs.get("tokens_out"),
                latency_ms=kwargs.get("latency_ms"),
                model_used=kwargs.get("model_used"),
            )

    try:
        asyncio.run(_save_to_db())
    except Exception as e:
        logger.error("Failed to save chat message to DB: %s", e)
