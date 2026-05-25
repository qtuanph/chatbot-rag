"""Chat service — session management, context preparation, message persistence.

Uses OpenAILike (9Router) via llama_index.core.Settings.llm for streaming.
Uses LlamaIndex retrieval pipeline (hybrid + TEI reranker) for RAG.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time as _time
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from llama_index.core import Settings
from llama_index.core.base.llms.types import ChatMessage, MessageRole

from app.core.config import settings
from app.modules.chat.repositories.repository import ChatRepository
from app.modules.chat.utils import ChatStore, compute_cost, normalize_query
from app.modules.chat.retrieval import retrieve_context

logger = logging.getLogger(__name__)


def _to_llama_role(role: str) -> MessageRole:
    role_map = {
        "system": MessageRole.SYSTEM,
        "user": MessageRole.USER,
        "assistant": MessageRole.ASSISTANT,
        "tool": MessageRole.TOOL,
    }
    return role_map.get((role or "").lower(), MessageRole.USER)


def build_answer(query: str, context: Any) -> dict:
    """Build the answer seed from RAG context."""
    from dataclasses import asdict as dc_asdict

    if not context or not context.nodes:
        return {
            "answer": (
                "Hiện tại tôi chưa có tài liệu nào để trả lời câu hỏi này. "
                "Vui lòng yêu cầu Admin upload thêm tài liệu vào hệ thống."
            ),
            "citations": [],
            "context": [],
        }

    sorted_nodes = sorted(
        context.nodes,
        key=lambda n: (n.document_id, n.section_id or "", -(n.score if n.score else 0.0)),
    )

    context_blocks = []
    citations = []
    seen_docs: set[str] = set()
    citation_idx = 0
    total_chars = 0
    max_chars = settings.retrieval_context_max_chars

    for node in sorted_nodes:
        doc_key = f"{node.document_id}:{node.section_id or node.node_id}"
        if doc_key not in seen_docs:
            seen_docs.add(doc_key)
            citation_idx += 1
            title = node.document_title or "Tài liệu"
            heading = node.heading or "Mục liên quan"
            page = f" (trang {node.page_range})" if node.page_range else ""
            block = f"{title} — {heading}{page}\n{node.full_text}"
            total_chars += len(block)
            if total_chars <= max_chars or len(seen_docs) <= 1:
                context_blocks.append(block)
                citations.append(
                    {
                        "document_id": node.document_id,
                        "node_id": node.node_id,
                        "title": node.document_title,
                        "heading": node.heading,
                        "page_range": node.page_range,
                        "index": citation_idx,
                    }
                )

    context_text = "\n\n".join(context_blocks)
    answer = f"Câu hỏi: {query}\n\nTài liệu tham khảo:\n{context_text}"

    return {"answer": answer, "citations": citations, "context": [dc_asdict(node) for node in sorted_nodes]}


def _fire_and_forget(coro: Any, error_msg: str = "Background task failed") -> None:
    async def _run():
        try:
            await coro
        except Exception as e:
            logger.warning("%s: %s", error_msg, e)

    asyncio.create_task(_run())


class ChatService:
    def __init__(self, repo: ChatRepository, store: ChatStore, user_memory_service: Any = None) -> None:
        self.repo = repo
        self.store = store
        self._user_memory_service = user_memory_service

    async def prepare_chat(self, *, user_id: str, query: str, session_id: str | None = None) -> dict:
        from app.modules.chat.utils import validate_query, deduplicate_citations, is_greeting

        _t0 = _time.monotonic()
        validate_query(query)
        scope_id = f"user:{user_id}"
        resolved_session_id = await self.resolve_session(user_id=user_id, session_id=session_id)
        self.validate_session_id(resolved_session_id)

        await self.get_or_create_session(session_id=resolved_session_id, user_id=user_id, query=query)
        logger.info("[PERF] Session setup: %.3fs", _time.monotonic() - _t0)

        _t1 = _time.monotonic()
        history_task = self.store.get_history(scope_id, resolved_session_id)
        if self._user_memory_service:
            memories_task = self._user_memory_service.format_memories_for_prompt(user_id)
            history, user_memories = await asyncio.gather(history_task, memories_task)
        else:
            history = await history_task
            user_memories = None
        logger.info("[PERF] History + memories: %.3fs", _time.monotonic() - _t1)

        if is_greeting(query):
            logger.info("Greeting detected, skipping RAG retrieval: query=%s", query[:50])
            return {
                "session_id": resolved_session_id,
                "scope_id": scope_id,
                "history": history,
                "assistant_seed": None,
                "citations": [],
                "user_memories": user_memories,
                "is_greeting": True,
            }

        queries = [query]

        _t4 = _time.monotonic()
        context = await self.retrieve_rag_context(self.repo.session, queries, resolved_session_id, 20)
        logger.info("[PERF] RAG retrieval: %.3fs", _time.monotonic() - _t4)

        _t5 = _time.monotonic()
        assistant_seed = build_answer(query, context)
        logger.info("[PERF] Build answer: %.3fs", _time.monotonic() - _t5)

        citations = deduplicate_citations(assistant_seed.get("citations") or [])

        logger.info("[PERF] prepare_chat TOTAL: %.3fs", _time.monotonic() - _t0)

        return {
            "session_id": resolved_session_id,
            "scope_id": scope_id,
            "history": history,
            "assistant_seed": assistant_seed,
            "citations": citations,
            "user_memories": user_memories,
        }

    async def stream_chat_events(
        self,
        *,
        user_id: str,
        query: str,
        prepared_chat: dict,
        thinking_mode: bool = False,
        start_time: float | None = None,
    ) -> AsyncGenerator[str, None]:
        from app.utils.cache import LLMResponseCache
        from app.modules.chat.retrieval.usage_tracker import track_usage

        session_id = prepared_chat["session_id"]
        history = prepared_chat["history"]
        citations = prepared_chat["citations"]

        if start_time is None:
            start_time = _time.monotonic()

        if prepared_chat.get("is_greeting"):
            greeting = self._random_greeting()
            yield f"data: {json.dumps({'chunk': greeting, 'done': False})}\n\n"
            message_id = await asyncio.shield(
                self.save_assistant_message(
                    session_id=session_id,
                    user_id=user_id,
                    role="assistant",
                    content=greeting,
                    citations=[],
                    tokens_in=0,
                    tokens_out=0,
                    latency_ms=0,
                    model_used="greeting",
                )
            )
            yield f"data: {json.dumps({'chunk': '', 'done': True, 'session_id': session_id, 'message_id': message_id, 'citations': [], 'stats': {'total_ms': 0, 'ttft_ms': 0, 'chars': len(greeting), 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0, 'estimated_cost_usd': 0, 'model': 'greeting'}})}\n\n"
            return

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

        seed = prepared_chat["assistant_seed"] or {}
        raw = seed.get("answer", "")
        if raw and "Tài liệu tham khảo:\n" in raw:
            formatted_context = raw[raw.index("Tài liệu tham khảo:\n") :]
        else:
            formatted_context = ""

        llm = Settings.llm
        messages: list[ChatMessage] = []
        for item in history:
            content = item.get("content", "") if isinstance(item, dict) else ""
            role = item.get("role", "user") if isinstance(item, dict) else "user"
            messages.append(ChatMessage(role=_to_llama_role(role), content=str(content or "")))

        system_prompt = (
            "Bạn là trợ lý hỗ trợ người dùng cuối, trả lời dựa trên tài liệu đã được nạp vào hệ thống. "
            "Chỉ dùng thông tin có trong ngữ cảnh tài liệu được cung cấp. "
            "Nếu chưa đủ chắc chắn, nói rõ phần chưa chắc và gợi ý 1-2 bước kiểm tra tiếp theo; không bịa thông tin. "
            "Trả lời tự nhiên, dễ hiểu, đi thẳng vào thao tác. "
            "Mặc định ngắn gọn (4-8 dòng), chỉ liệt kê nhiều bước khi người dùng yêu cầu chi tiết. "
            "Được phép dùng bảng Markdown khi cần so sánh/tổng hợp, và dùng sơ đồ text/ASCII khi cần mô tả luồng. "
            "Sau bảng/sơ đồ, luôn kèm giải thích ngắn. "
            "Không dùng ký hiệu trích dẫn kiểu [1], [Nguồn], [Source]. "
            "Chỉ nêu số mục/chương/trang khi có trong ngữ cảnh hiện tại. "
            "Nếu không thấy rõ số mục/chương/trang, chỉ ghi tham chiếu chung: 'Theo tài liệu đã cung cấp'."
        )
        if formatted_context:
            system_prompt += f"\n\n{formatted_context}"
        if prepared_chat.get("user_memories"):
            system_prompt += f"\n\n{prepared_chat['user_memories']}"

        full_messages: list[ChatMessage] = [ChatMessage(role=MessageRole.SYSTEM, content=system_prompt)] + messages

        usage_info = {}
        model_name = getattr(llm, "model", "unknown")
        stream_failed = False

        try:
            resp_gen = await llm.astream_chat(full_messages)
            async for chunk in resp_gen:
                if first_chunk_time is None:
                    first_chunk_time = _time.monotonic()
                delta = (
                    chunk.delta if hasattr(chunk, "delta") else (chunk.text if hasattr(chunk, "text") else str(chunk))
                )
                full_answer += delta
                yield f"data: {json.dumps({'chunk': delta, 'done': False})}\n\n"
                if hasattr(chunk, "additional_kwargs"):
                    usage_info.update(chunk.additional_kwargs)
        except Exception as e:
            stream_failed = True
            logger.warning("LLM stream failed, fallback to non-stream response: %s", e, exc_info=True)

        if stream_failed:
            try:
                resp = await llm.achat(full_messages)
                content = getattr(resp, "message", None)
                fallback_text = ""
                if content is not None and hasattr(content, "content"):
                    fallback_text = str(content.content or "")
                if not fallback_text and hasattr(resp, "text"):
                    fallback_text = str(resp.text or "")
                if not fallback_text:
                    fallback_text = "Mình bị gián đoạn kết nối khi trả lời. Bạn gửi lại câu hỏi này giúp mình nhé."
                if not full_answer:
                    full_answer = fallback_text
                    yield f"data: {json.dumps({'chunk': fallback_text, 'done': False})}\n\n"
                if hasattr(resp, "additional_kwargs") and isinstance(resp.additional_kwargs, dict):
                    usage_info.update(resp.additional_kwargs)
            except Exception as e2:
                logger.error("LLM non-stream fallback also failed: %s", e2, exc_info=True)
                if not full_answer:
                    full_answer = "Mình bị gián đoạn kết nối tới AI. Bạn thử lại sau vài giây nhé."
                    yield f"data: {json.dumps({'chunk': full_answer, 'done': False})}\n\n"

        ai_done_time = _time.monotonic()
        clean_answer = full_answer.strip()

        prompt_tokens = usage_info.get("prompt_tokens", 0)
        completion_tokens = usage_info.get("completion_tokens", 0)
        ttft_ms = int((first_chunk_time - start_time) * 1000) if first_chunk_time else 0

        provider = type("obj", (), {"last_usage": usage_info, "model_name": model_name})()

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
                        "model": model_name,
                    },
                }
                _fire_and_forget(
                    llm_cache.set(normalized_query, None, cache_data), "[LLM-CACHE] Async cache set failed"
                )
            except Exception as e:
                logger.warning("[LLM-CACHE] Cache store failed: %s", e)

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
                    model_used=model_name,
                    vector_ids=vids,
                )
            )
            track_usage(provider, endpoint="chat", user_id=user_id, session_id=session_id, message_id=message_id)

            if settings.ragas_evaluation_enabled:
                _fire_and_forget(
                    self._run_ragas_evaluation(query, clean_answer, prepared_chat), "[RAGAS] Async evaluation failed"
                )
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
                "model": model_name,
            },
        }
        if finalize_error:
            final_data["error"] = finalize_error
        yield f"data: {json.dumps(final_data)}\n\n"

    async def retrieve_rag_context(
        self, session: AsyncSession, queries: list[str], session_id: str | None = None, limit: int = 20
    ) -> Any:
        positive_ids, negative_ids = [], []
        if session_id:
            positive_ids, negative_ids = await ChatRepository(session).get_feedback_signals(session_id)

        return await retrieve_context(
            queries,
            limit=limit,
            positive_point_ids=positive_ids,
            negative_point_ids=negative_ids,
        )

    # ── Session management ──────────────────────────────────────────

    async def resolve_session(self, *, user_id: str, session_id: str | None) -> str:
        scope_id = f"user:{user_id}"
        resolved = session_id or await self.store.get_active_session(scope_id) or str(uuid4())
        await self.store.set_active_session(scope_id, resolved)
        return resolved

    @staticmethod
    def validate_session_id(session_id: str) -> None:
        try:
            UUID(session_id)
        except ValueError:
            raise ValueError("Invalid session ID format") from None

    async def get_or_create_session(self, *, session_id: str, user_id: str, query: str) -> dict:
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

    async def _run_ragas_evaluation(self, query: str, answer: str, prepared_chat: dict) -> None:
        try:
            from app.modules.analytics.ragas_evaluator import RagasEvaluator

            contexts = []
            if prepared_chat.get("assistant_seed", {}).get("context"):
                for ctx in prepared_chat["assistant_seed"]["context"]:
                    if isinstance(ctx, dict):
                        contexts.append(ctx.get("full_text", "")[:500])

            evaluator = RagasEvaluator()
            metrics = await evaluator.evaluate(query=query, answer=answer, contexts=contexts)

            logger.info(
                "[RAGAS] faithfulness=%.2f answer_relevancy=%.2f context_relevancy=%.2f overall=%.2f",
                metrics.faithfulness,
                metrics.answer_relevancy,
                metrics.context_relevancy,
                metrics.overall_score,
            )
        except Exception as e:
            logger.warning("[RAGAS] Evaluation failed: %s", e)

    async def set_message_feedback(self, message_id: str, user_id: str, feedback: int) -> dict:
        updated = await self.repo.update_feedback(message_id, feedback)
        if not updated:
            raise ValueError("Message not found")
        if feedback == -1:
            await self._clear_cache_for_dislike(message_id)
        logger.info("Feedback recorded: user=%s message=%s feedback=%d", user_id[:8], message_id[:8], feedback)
        return updated

    async def _clear_cache_for_dislike(self, message_id: str) -> None:
        query = await self.repo.get_previous_user_message(message_id)
        if not query:
            return

        from app.modules.chat.utils import normalize_query
        from app.utils.cache.llm_response_cache import LLMResponseCache

        normalized = normalize_query(query) if settings.query_normalize_enabled else query
        llm_cache = LLMResponseCache(redis_client=self.store.client)
        await llm_cache.delete(normalized)

        try:
            keys = []
            async for key in self.store.client.scan_iter("cache:semantic:*"):
                keys.append(key)
            if keys:
                await self.store.client.delete(*keys)
                logger.info("[CACHE] Cleared %d semantic cache entries on dislike", len(keys))
        except Exception as e:
            logger.warning("[CACHE] Failed to clear semantic cache: %s", e)

    @staticmethod
    def _random_greeting() -> str:
        import random

        greetings = [
            "Chào bạn! Tôi có thể giúp gì cho bạn hôm nay?",
            "Xin chào! Rất vui được gặp bạn. Bạn cần tôi hỗ trợ gì không?",
            "Chào bạn! Hãy cho tôi biết bạn đang cần tìm hiểu về vấn đề gì nhé.",
            "Xin chào! Tôi là trợ lý AI, sẵn sàng giải đáp thắc mắc của bạn.",
            "Chào bạn! Rất vui được trò chuyện cùng bạn. Bạn muốn hỏi gì về tài liệu?",
        ]
        return random.choice(greetings)

    # ── Session listing ─────────────────────────────────────────────

    async def create_session(self, *, user_id: str) -> dict:
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



