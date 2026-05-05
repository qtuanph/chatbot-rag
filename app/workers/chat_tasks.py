"""Celery tasks for chat operations — offloaded from API to avoid blocking SSE stream."""

import asyncio
import logging
from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.utils.chat_store import ChatStore

logger = logging.getLogger(__name__)


def _get_chat_store() -> ChatStore:
    from app.core.redis import redis_client

    return ChatStore(redis_client)


async def _save_message_async(
    *,
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    citations: list[dict] | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    latency_ms: int | None = None,
    model_used: str | None = None,
) -> None:
    """Async implementation of message saving."""
    from app.repositories.chat_repository import ChatRepository

    async with AsyncSessionLocal() as session:
        repo = ChatRepository(session)
        await repo.create_message(
            session_id=session_id,
            role=role,
            content=content,
            citations=citations,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            model_used=model_used,
        )

    scope_id = f"user:{user_id}"
    chat_store = _get_chat_store()
    await chat_store.append_message(scope_id, session_id, role, content)


def save_message_now(**kwargs) -> None:
    """Synchronous entry point for Celery or SSE."""
    try:
        asyncio.run(_save_message_async(**kwargs))
    except Exception as e:
        logger.error("Failed to save chat message: %s", e)


@celery_app.task(
    name="app.workers.chat_tasks.save_chat_message_task",
    acks_late=True,
    ignore_result=True,
)
def save_chat_message_task(**kwargs) -> None:
    """Celery task: save chat message asynchronously."""
    save_message_now(**kwargs)
