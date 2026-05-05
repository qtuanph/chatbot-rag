"""Chat service — session management, context preparation, message persistence."""

from __future__ import annotations

import asyncio
import json
import logging
import time as _time
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ai import build_ai_provider
from app.adapters.ai.google import strip_reasoning
from app.core.config import settings
from app.repositories.chat_repository import ChatRepository
from app.utils.chat_store import ChatStore

logger = logging.getLogger(__name__)


class ChatService:
    """Business logic for chat sessions, context preparation, and message persistence."""

    def __init__(self, repo: ChatRepository, store: ChatStore, user_memory_service: Any = None) -> None:
        self.repo = repo
        self.store = store
        self._user_memory_service = user_memory_service

    async def prepare_chat(self, *, user_id: str, query: str, session_id: str | None = None) -> dict:
        """Prepare full chat context: validate → session → retrieval → answer seed."""
        from app.utils.chat_utils import validate_query

        validate_query(query)
        scope_id = f"user:{user_id}"
        resolved_session_id = await self.resolve_session(user_id=user_id, session_id=session_id)
        self.validate_session_id(resolved_session_id)

        await self.get_or_create_session(session_id=resolved_session_id, user_id=user_id, query=query)

        # Parallel fetch for history and memories
        history_task = self.store.get_history(scope_id, resolved_session_id)
        if self._user_memory_service:
            memories_task = self._user_memory_service.format_memories_for_prompt(user_id)
            history, user_memories = await asyncio.gather(history_task, memories_task)
        else:
            history = await history_task
            user_memories = None

        # Multi-query expansion
        queries = [query]
        if settings.retrieval_query_expansion_enabled:
            from app.services.retrieval.expansion_service import expand_query

            try:
                queries = await asyncio.wait_for(expand_query(query), timeout=3.0)
            except asyncio.TimeoutError:
                logger.warning("Query expansion timed out, using original query.")

        # RAG retrieval
        context = await self.retrieve_rag_context(self.repo.session, queries, resolved_session_id, 20)

        from app.utils.retrieval_utils import build_answer

        assistant_seed = build_answer(query, context)

        from app.utils.chat_utils import deduplicate_citations

        citations = deduplicate_citations(assistant_seed.get("citations") or [])

        return {
            "session_id": resolved_session_id,
            "scope_id": scope_id,
            "history": history,
            "assistant_seed": assistant_seed,
            "citations": citations,
            "user_memories": user_memories,
        }

    async def stream_chat_events(self, *, user_id: str, query: str, prepared_chat: dict) -> AsyncGenerator[str, None]:
        """Generate SSE events for chat."""
        provider = build_ai_provider()
        session_id = prepared_chat["session_id"]
        history = prepared_chat["history"]
        citations = prepared_chat["citations"]

        full_answer = ""
        start_time = _time.monotonic()
        _stream_buf = ""

        async for chunk in provider.chat_stream(
            [{"role": i["role"], "content": i["content"]} for i in history],
            context=prepared_chat["assistant_seed"].get("context") or [],
            citations=citations,
            user_memories=prepared_chat["user_memories"],
        ):
            full_answer += chunk
            _stream_buf += chunk
            # Word-boundary buffering: only yield when buffer ends at a
            # safe boundary (space, newline, punctuation). This prevents
            # Vietnamese compound words from appearing concatenated when
            # BPE tokenizer splits them across streaming chunks.
            if _stream_buf and _stream_buf[-1] in (" ", "\n", "\t", ".", ",", "!", "?", ";", ":", ")", "]", "}", "…"):
                yield f"data: {json.dumps({'chunk': _stream_buf, 'done': False})}\n\n"
                _stream_buf = ""

        # Flush remaining buffer (partial word at end of stream)
        if _stream_buf:
            yield f"data: {json.dumps({'chunk': _stream_buf, 'done': False})}\n\n"
            _stream_buf = ""

        ai_done_time = _time.monotonic()
        clean_answer = strip_reasoning(full_answer.strip())
        usage = getattr(provider, "last_usage", {})

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        # Non-blocking finalization
        vids = [c["node_id"] for c in citations if "node_id" in c]
        try:
            await self.save_assistant_message(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=clean_answer,
                citations=citations,
                tokens_in=prompt_tokens,
                tokens_out=completion_tokens,
                latency_ms=int((ai_done_time - start_time) * 1000),
                model_used=provider.model_name,
                vector_ids=vids,
            )
            self.enqueue_memory_extraction(user_id=user_id, user_message=query, assistant_response=clean_answer)
        except Exception as e:
            logger.error("Failed to finalize chat session: %s", e)

        from app.utils.chat_utils import compute_cost

        final_data = {
            "chunk": "",
            "done": True,
            "session_id": session_id,
            "citations": citations,
            "stats": {
                "total_ms": int((ai_done_time - start_time) * 1000),
                "chars": len(clean_answer),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "estimated_cost_usd": compute_cost(prompt_tokens, completion_tokens),
                "model": provider.model_name,
            },
        }
        yield f"data: {json.dumps(final_data)}\n\n"

    # ── RAG retrieval ────────────────────────────────────────────────

    @staticmethod
    async def retrieve_rag_context(
        session: AsyncSession, queries: list[str], session_id: str | None = None, limit: int = 20
    ) -> Any:
        """Run RAG retrieval. Returns RagContext."""
        from app.services.retrieval.retrieval_service import retrieve_context

        positive_ids, negative_ids = [], []
        if session_id:
            positive_ids, negative_ids = await ChatRepository(session).get_feedback_signals(session_id)

        return await retrieve_context(
            session, queries, limit, positive_point_ids=positive_ids, negative_point_ids=negative_ids
        )

    # ── Session management ──────────────────────────────────────────

    async def resolve_session(self, *, user_id: str, session_id: str | None) -> str:
        """Resolve or create a session ID. Returns session_id."""
        scope_id = f"user:{user_id}"
        resolved = session_id or await self.store.get_active_session(scope_id) or str(uuid4())
        await self.store.set_active_session(scope_id, resolved)
        return resolved

    @staticmethod
    def validate_session_id(session_id: str) -> None:
        """Validate UUID format of session ID. Raises ValueError."""
        try:
            UUID(session_id)
        except ValueError:
            raise ValueError("Invalid session ID format") from None

    async def get_or_create_session(self, *, session_id: str, user_id: str, query: str) -> dict:
        """Get existing session or create new. Raises ValueError on ownership mismatch."""
        session = await self.repo.get_session(session_id)

        if session is None:
            logger.info("Creating new chat session: session_id=%s, user_id=%s", session_id, user_id)
            session = await self.repo.create_session(session_id=session_id, user_id=user_id, title="Active chat")
        elif session.get("user_id") and str(session["user_id"]) != user_id:
            raise ValueError("Chat session does not belong to this user")

        if session.get("title") == "Active chat":
            new_title = query[:80] + ("..." if len(query) > 80 else "")
            await self.repo.update_session_title(session_id, new_title)
            session["title"] = new_title

        scope_id = f"user:{user_id}"
        await self.store.append_message(scope_id, session_id, "user", query)
        logger.info("Saving user message to database: session_id=%s, user_id=%s", session_id, user_id)
        await self.repo.save_user_message(session_id, query)
        logger.info("User message saved successfully: session_id=%s", session_id)

        if not await self.store.history_exists(scope_id, session_id):
            db_msgs = await self.repo.get_messages_for_history(session_id)
            await self.store.hydrate_from_db(scope_id, session_id, db_msgs)

        return session

    # ── Message persistence ─────────────────────────────────────────

    async def save_assistant_message(self, **kwargs) -> None:
        """Save assistant message to PostgreSQL + Redis."""
        try:
            session_id = kwargs.get("session_id")
            user_id = kwargs.get("user_id")
            logger.info("Saving assistant message: session_id=%s, user_id=%s, role=%s", session_id, user_id, kwargs.get("role"))
            await self.repo.create_message(**kwargs)
            logger.info("Successfully saved assistant message: session_id=%s", session_id)
        except Exception as e:
            logger.error("Failed to save chat message: %s", e, exc_info=True)
            raise RuntimeError("Failed to persist assistant message") from e

        try:
            scope_id = f"user:{kwargs['user_id']}"
            await self.store.append_message(scope_id, kwargs["session_id"], "assistant", kwargs["content"])
        except Exception as e:
            logger.warning("Failed to cache chat message in Redis: %s", e)

    async def set_message_feedback(self, message_id: str, user_id: str, feedback: int) -> dict:
        """Record user feedback for a message. Raises ValueError if not found or unauthorized."""
        updated = await self.repo.update_feedback(message_id, feedback)
        if not updated:
            raise ValueError("Message not found")
        logger.info("Feedback recorded: user=%s message=%s feedback=%d", user_id[:8], message_id[:8], feedback)
        return updated

    @staticmethod
    def enqueue_memory_extraction(*, user_id: str, user_message: str, assistant_response: str) -> None:
        """Dispatch durable memory extraction after a chat turn."""
        try:
            from app.workers.memory_tasks import extract_memories_task

            extract_memories_task.delay(
                user_id=user_id, user_message=user_message, assistant_response=assistant_response
            )
        except Exception as e:
            logger.debug("Memory extraction dispatch failed (best-effort): %s", e)

    # ── Session listing ─────────────────────────────────────────────

    async def create_session(self, *, user_id: str) -> dict:
        """Create a new empty chat session."""
        session_id = str(uuid4())
        session = await self.repo.create_session(session_id=session_id, user_id=user_id, title="Active chat")
        return {
            "session_id": session["id"],
            "title": session["title"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "message_count": 0,
        }

    async def list_sessions(self, user_id: str) -> list[dict]:
        return await self.repo.list_sessions_with_counts(user_id)

    # ── Message listing ─────────────────────────────────────────────

    async def list_messages(self, *, session_id: str, user_id: str, limit: int = 20, offset: int = 0) -> dict:
        """List messages for a session. Raises ValueError if not found or ownership mismatch."""
        session = await self.repo.get_session(session_id)
        if session is None:
            raise ValueError("Chat session not found")
        if session.get("user_id") and str(session["user_id"]) != user_id:
            raise ValueError("Chat session does not belong to this user")

        total = await self.repo.count_messages(session_id)
        limit = max(1, min(limit, 100))
        effective_offset = max(0, total - offset - limit)
        effective_limit = min(limit, total - offset)

        if effective_limit <= 0:
            return {"messages": [], "total": total, "has_more": False}

        messages = await self.repo.list_messages(session_id, offset=effective_offset, limit=effective_limit)
        return {
            "messages": [
                {
                    "id": m["id"],
                    "role": m["role"],
                    "content": m["content"],
                    "citations": m.get("citations") or [],
                    "feedback": m.get("feedback", 0),
                    "created_at": m["created_at"],
                }
                for m in messages
            ],
            "total": total,
            "has_more": effective_offset > 0,
        }
