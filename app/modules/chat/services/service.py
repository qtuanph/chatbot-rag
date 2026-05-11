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
from app.modules.chat.repositories.repository import ChatRepository
from app.modules.chat.utils import ChatStore, compute_cost, normalize_query
from app.modules.chat.retrieval import build_answer

logger = logging.getLogger(__name__)


class ChatService:
    """Business logic for chat sessions, context preparation, and message persistence."""

    def __init__(self, repo: ChatRepository, store: ChatStore, user_memory_service: Any = None) -> None:
        self.repo = repo
        self.store = store
        self._user_memory_service = user_memory_service

    async def prepare_chat(self, *, user_id: str, query: str, session_id: str | None = None) -> dict:
        """Prepare full chat context: validate → session → retrieval → answer seed."""
        from app.modules.chat.utils import validate_query, deduplicate_citations

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
            from app.modules.chat.retrieval.expansion_service import expand_query

            try:
                queries = await asyncio.wait_for(expand_query(query), timeout=3.0)
            except asyncio.TimeoutError:
                logger.warning("Query expansion timed out, using original query.")

        # RAG retrieval
        context = await self.retrieve_rag_context(self.repo.session, queries, resolved_session_id, 20)

        assistant_seed = build_answer(query, context)

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
        from app.core.config import settings
        from app.utils.cache import LLMResponseCache

        provider = build_ai_provider()
        session_id = prepared_chat["session_id"]
        history = prepared_chat["history"]
        citations = prepared_chat["citations"]

        full_answer = ""
        start_time = _time.monotonic()
        first_chunk_time: float | None = None

        normalized_query = normalize_query(query) if settings.query_normalize_enabled else query

        llm_cache = None
        if settings.llm_cache_enabled:
            try:
                llm_cache = LLMResponseCache(redis_client=self.store.client)
                cached = await llm_cache.get(normalized_query, None)
                if cached:
                    logger.info("[LLM-CACHE] Cache HIT - returning cached response")
                    cache_hit_time = _time.monotonic()
                    cached_answer = cached.get("answer", "")
                    cached_stats = cached.get("stats", {})
                    cached_citations = cached.get("citations", citations)

                    if cached_answer:
                        yield f"data: {json.dumps({'chunk': cached_answer, 'done': False})}\n\n"

                    cache_latency_ms = int((cache_hit_time - start_time) * 1000)

                    # Persist cached response to DB FIRST to get real message_id
                    cached_message_id: str | None = None
                    try:
                        cached_message_id = await asyncio.shield(
                            self.save_assistant_message(
                                session_id=session_id,
                                user_id=user_id,
                                role="assistant",
                                content=cached_answer,
                                citations=cached_citations,
                                tokens_in=cached_stats.get("prompt_tokens", 0),
                                tokens_out=cached_stats.get("completion_tokens", 0),
                                latency_ms=cache_latency_ms,
                                model_used=cached_stats.get("model", "cached"),
                            )
                        )
                    except Exception as e:
                        logger.error("Failed to persist cached assistant message: %s", e, exc_info=True)

                    final_data = {
                        "chunk": "",
                        "done": True,
                        "session_id": session_id,
                        "message_id": cached_message_id,
                        "citations": cached_citations,
                        "stats": {
                            "total_ms": cache_latency_ms,
                            "ttft_ms": 0,
                            "chars": len(cached_answer),
                            "prompt_tokens": cached_stats.get("prompt_tokens", 0),
                            "completion_tokens": cached_stats.get("completion_tokens", 0),
                            "total_tokens": cached_stats.get("total_tokens", 0),
                            "estimated_cost_usd": cached_stats.get("estimated_cost_usd", 0),
                            "model": cached_stats.get("model", "cached"),
                            "cache_hit": True,
                        },
                    }
                    yield f"data: {json.dumps(final_data)}\n\n"
                    return
            except Exception as e:
                logger.warning("[LLM-CACHE] Cache check failed: %s", e)

        async for chunk in provider.chat_stream(
            [{"role": i["role"], "content": i["content"]} for i in history],
            context=prepared_chat["assistant_seed"].get("context") or [],
            citations=citations,
            user_memories=prepared_chat["user_memories"],
        ):
            if first_chunk_time is None:
                first_chunk_time = _time.monotonic()
            full_answer += chunk
            # Immediate yield to prevent word-concatenation and "stuck" feeling in Vietnamese
            yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"

        ai_done_time = _time.monotonic()
        clean_answer = strip_reasoning(full_answer.strip())
        usage = getattr(provider, "last_usage", {})

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        ttft_ms = int((first_chunk_time - start_time) * 1000) if first_chunk_time else 0

        if llm_cache and clean_answer:
            try:
                cache_data = {
                    "answer": clean_answer,
                    "citations": citations,
                    "stats": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "estimated_cost_usd": compute_cost(prompt_tokens, completion_tokens),
                        "model": provider.model_name,
                    },
                }
                await llm_cache.set(normalized_query, None, cache_data)
                logger.debug("[LLM-CACHE] Stored response for query: %s", normalized_query[:50])
            except Exception as e:
                logger.warning("[LLM-CACHE] Cache store failed: %s", e)

        # Finalize persistence after the streamed answer is complete.
        finalize_error: str | None = None
        vids = [c["node_id"] for c in citations if "node_id" in c]
        message_id: str | None = None
        try:
            message_id = await asyncio.shield(
                self.save_assistant_message(
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
            )
            self.enqueue_memory_extraction(user_id=user_id, user_message=query, assistant_response=clean_answer)
        except Exception as e:
            finalize_error = "Failed to persist assistant message"
            logger.error("Failed to finalize chat session: %s", e, exc_info=True)

        final_data = {
            "chunk": "",
            "done": True,
            "session_id": session_id,
            "message_id": message_id,
            "citations": citations,
            "stats": {
                "total_ms": int((ai_done_time - start_time) * 1000),
                "ttft_ms": ttft_ms,
                "chars": len(clean_answer),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "estimated_cost_usd": compute_cost(prompt_tokens, completion_tokens),
                "model": provider.model_name,
            },
        }
        if finalize_error:
            final_data["error"] = finalize_error
        yield f"data: {json.dumps(final_data)}\n\n"

    # ── RAG retrieval ────────────────────────────────────────────────

    async def retrieve_rag_context(
        self, session: AsyncSession, queries: list[str], session_id: str | None = None, limit: int = 20
    ) -> Any:
        """Run RAG retrieval. Returns RagContext."""
        from app.modules.chat.retrieval.retrieval_service import RetrievalService

        positive_ids, negative_ids = [], []
        if session_id:
            positive_ids, negative_ids = await ChatRepository(session).get_feedback_signals(session_id)

        # Use the class-based service with the same loop-safe client
        retrieval_service = RetrievalService(redis_client=self.store.client)
        return await retrieval_service.retrieve_context(
            session,
            queries,
            limit,
            positive_point_ids=positive_ids,
            negative_point_ids=negative_ids,
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

        logger.info("Saving user message to database: session_id=%s, user_id=%s", session_id, user_id)
        await self.repo.save_user_message(session_id, query)
        logger.info("User message saved successfully: session_id=%s", session_id)

        scope_id = f"user:{user_id}"
        try:
            await self.store.append_message(scope_id, session_id, "user", query)
        except Exception as e:
            logger.warning("Failed to cache user message in Redis: %s", e)

        if not await self.store.history_exists(scope_id, session_id):
            db_msgs = await self.repo.get_messages_for_history(session_id)
            await self.store.hydrate_from_db(scope_id, session_id, db_msgs)

        return session

    # ── Message persistence ─────────────────────────────────────────

    async def save_assistant_message(
        self,
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
        vector_ids: list[str] | None = None,
    ) -> str:
        """Save assistant message to PostgreSQL + Redis. Returns the message_id."""
        msg_dict: dict
        try:
            logger.info("Saving assistant message: session_id=%s, user_id=%s, role=%s", session_id, user_id, role)
            msg_dict = await self.repo.create_message(
                session_id=session_id,
                role=role,
                content=content,
                citations=citations,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                model_used=model_used,
                vector_ids=vector_ids,
            )
            message_id = msg_dict["id"]
            logger.info("Successfully saved assistant message: session_id=%s, message_id=%s", session_id, message_id)
        except Exception as e:
            logger.error("Failed to save chat message: %s", e, exc_info=True)
            raise RuntimeError("Failed to persist assistant message") from e

        try:
            scope_id = f"user:{user_id}"
            await self.store.append_message(scope_id, session_id, "assistant", content)
        except Exception as e:
            logger.warning("Failed to cache chat message in Redis: %s", e)

        return message_id

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
            from app.modules.chat.tasks.memory_tasks import extract_memories_task

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
