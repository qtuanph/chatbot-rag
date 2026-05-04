"""Celery tasks for chat operations — offloaded from API to avoid blocking SSE stream."""

import logging

from app.core.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def save_message_now(
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
    """Synchronous save — safe to call from SSE generator before yielding done:true."""
    from app.repositories.chat_repository import ChatRepository
    from app.utils.chat_store import ChatStore

    with SessionLocal() as session:
        repo = ChatRepository(session)
        repo.create_message(
            session_id=session_id,
            role=role,
            content=content,
            citations=citations,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            model_used=model_used,
        )

    store = ChatStore()
    scope_id = f"user:{user_id}"
    store.append_message(scope_id, session_id, role, content)


@celery_app.task(
    name="app.workers.chat_tasks.save_chat_message_task",
    acks_late=True,
    ignore_result=True,
)
def save_chat_message_task(**kwargs) -> None:
    """Celery wrapper — delegates to save_message_now for backward compatibility."""
    save_message_now(**kwargs)
