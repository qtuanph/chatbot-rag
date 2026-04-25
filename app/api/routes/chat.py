from __future__ import annotations

import asyncio
import json
import logging
import time as _time
from uuid import UUID, uuid4
from typing import Any, AsyncGenerator
from sqlalchemy import func

import nh3

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import AuthContext, get_auth_context
from app.adapters.ai import build_ai_provider
from app.adapters.ai.google import strip_reasoning
from app.core.config import settings
from app.core import http_errors
from app.db.session import SessionLocal
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import ChatRequest
from app.services.chat.store import ChatStore
from app.services.chat.memory import UserMemoryService
from app.services.retrieval.rag import build_answer, retrieve_context
from app.services.auth.throttle import RequestThrottle


router = APIRouter(tags=["chat"])
store = ChatStore()
memory_service = UserMemoryService()
provider = build_ai_provider()
throttle = RequestThrottle()
logger = logging.getLogger(__name__)

# Track background tasks to prevent GC
_background_tasks: set[asyncio.Task] = set()


def _deduplicate_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Group citations by document_id, merge page ranges into compact format.

    Returns one citation per document with merged page ranges like "1, 3-5, 7-9".
    """
    if not citations:
        return []

    # Group by document_id
    doc_groups: dict[str, list[dict]] = {}
    doc_titles: dict[str, str] = {}
    for citation in citations:
        doc_id = citation.get("document_id", "")
        if doc_id not in doc_groups:
            doc_groups[doc_id] = []
            doc_titles[doc_id] = citation.get("title", "Tài liệu")
        doc_groups[doc_id].append(citation)

    result = []
    for doc_id, cites in doc_groups.items():
        # Collect all page numbers
        pages: set[int] = set()
        for c in cites:
            pr = c.get("page_range")
            if pr:
                try:
                    # Handle ranges like "3-5" or single "7"
                    parts = str(pr).split("-")
                    start = int(parts[0].strip())
                    end = int(parts[-1].strip())
                    pages.update(range(start, end + 1))
                except (ValueError, IndexError):
                    pass

        # Merge consecutive pages into ranges
        page_display = ""
        if pages:
            sorted_pages = sorted(pages)
            ranges: list[str] = []
            range_start = sorted_pages[0]
            range_end = sorted_pages[0]
            for p in sorted_pages[1:]:
                if p == range_end + 1:
                    range_end = p
                else:
                    ranges.append(f"{range_start}" if range_start == range_end else f"{range_start}-{range_end}")
                    range_start = p
                    range_end = p
            ranges.append(f"{range_start}" if range_start == range_end else f"{range_start}-{range_end}")
            page_display = ", ".join(ranges)

        result.append({
            "document_id": doc_id,
            "title": doc_titles.get(doc_id, "Tài liệu"),
            "pages": page_display,
        })

    return result


def _validate_query(query: str) -> None:
    """
    Validate query input for security and length.
    Raises HTTPException if validation fails.

    Args:
        query: User query string

    Raises:
        HTTPException: If query is invalid
    """
    if not query or not query.strip():
        raise http_errors.bad_request("Query cannot be empty")

    if len(query) > 5000:
        raise http_errors.bad_request("Query too long (max 5000 characters)")

    # HTML sanitization — reject queries containing HTML tags
    sanitized = nh3.clean(query, tags=set(), attributes=set())
    if sanitized != query:
        raise http_errors.bad_request("Query contains invalid characters")


def _build_user_friendly_error(error: Exception) -> str:
    """
    Convert technical errors to user-friendly Vietnamese messages.

    Args:
        error: Exception instance

    Returns:
        User-friendly error message in Vietnamese
    """
    error_str = str(error).lower()

    if "timeout" in error_str or "timed out" in error_str:
        return "AI Model phản hồi quá chậm. Vui lòng thử câu hỏi ngắn hơn hoặc thử lại sau."
    elif "rate limit" in error_str or "429" in error_str:
        return "Đã đạt giới hạn request. Vui lòng chờ một chút rồi thử lại."
    elif "safety" in error_str or "blocked" in error_str:
        return "Nội dung không được phép. Vui lòng thử câu hỏi khác."
    elif "connection" in error_str:
        return "Lỗi kết nối với AI Model. Vui lòng kiểm tra mạng và thử lại."
    else:
        return "Lỗi không xác định. Vui lòng thử lại sau."


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, auth: AuthContext = Depends(get_auth_context)):
    """
    Streaming chat endpoint - yields chunks as AI generates response.
    Returns Server-Sent Events (SSE) format.

    Features:
    - Client disconnect detection (stops generation immediately)
    - AI provider timeouts handled gracefully
    - Error propagation in stream
    - Automatic retry on transient errors
    - Proper SSE format with double newlines
    - Cititions deduplication
    - Session management

    SSE Format:
        data: {"chunk": "text", "done": false}
        data: {"chunk": "", "done": true, "session_id": "...", "citations": [...]}
        data: {"chunk": "", "done": true, "error": "..."}
    """
    # Rate limiting
    if not throttle.allow(
        f"throttle:chat:{auth.user_id}",
        limit=settings.effective_rate_limit(100),
        window_seconds=60,
    ):
        raise http_errors.too_many_requests(
            "Too many chat requests. Please wait a moment before trying again."
        )

    # Validate query input
    _validate_query(request.query)

    scope_id = f"user:{auth.user_id}"
    session_id = request.session_id or store.get_active_session(scope_id) or str(uuid4())
    store.set_active_session(scope_id, session_id)

    # Validate UUID format before DB query
    try:
        UUID(session_id)
    except ValueError:
        raise http_errors.bad_request("Invalid session ID format")

    t_start = _time.monotonic()

    with SessionLocal() as session:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            chat_session = ChatSession(id=session_id, user_id=auth.user_id, title="Active chat")
            session.add(chat_session)
            session.commit()
        elif str(chat_session.user_id) != auth.user_id:
            raise http_errors.forbidden("Chat session does not belong to this user")

        # Auto-title from first user message
        if chat_session.title == "Active chat":
            chat_session.title = request.query[:80] + ("..." if len(request.query) > 80 else "")
            session.commit()

        store.append_message(scope_id, session_id, "user", request.query)

        # Save user message to PostgreSQL for persistence across sessions
        session.add(ChatMessage(session_id=session_id, role="user", content=request.query))
        chat_session.updated_at = func.now()
        session.commit()

        # Hydrate Redis from DB only if TTL expired (Redis empty)
        if not store.history_exists(scope_id, session_id):
            db_msgs = session.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at.asc()).all()
            db_dicts = [{"role": m.role, "content": m.content} for m in db_msgs]
            store.hydrate_from_db(scope_id, session_id, db_dicts)

        t_session = _time.monotonic()
        logger.info("[PERF] Session setup: %.3fs", t_session - t_start)

        try:
            # Multi-query expansion: generate query variants for broader recall
            queries = [request.query]
            if settings.retrieval_query_expansion_enabled:
                from app.services.retrieval.query_expand import expand_query
                queries = await asyncio.wait_for(
                    expand_query(request.query),
                    timeout=3.0,
                )
                logger.info(
                    "[PERF] Query expansion: %d variants in %.3fs",
                    len(queries), _time.monotonic() - t_session,
                )

            context = retrieve_context(session, queries, limit=20)

            t_retrieve = _time.monotonic()
            logger.info("[PERF] retrieve_context: %.3fs (%d nodes)", t_retrieve - t_session, len(context.nodes))

            assistant_seed = build_answer(request.query, context)

            t_build = _time.monotonic()
            logger.info("[PERF] build_answer: %.3fs", t_build - t_retrieve)

            history = store.get_history(scope_id, session_id)

            # Deduplicate and clean citations
            raw_citations = assistant_seed.get("citations") or []
            citations = _deduplicate_citations(raw_citations)

            # Load user memories for personalized system instruction
            user_memories = memory_service.format_memories_for_prompt(auth.user_id)

            t_memories = _time.monotonic()
            logger.info("[PERF] Memories + history: %.3fs", t_memories - t_build)
            logger.info("[PERF] Total prep before AI: %.3fs", t_memories - t_start)

        except Exception as e:
            logger.error("Error preparing chat context: %s", e, exc_info=True)
            raise http_errors.internal_server_error(
                "Failed to prepare chat context. Please try again."
            ) from None

    async def generate() -> AsyncGenerator[str, None]:
        """
        Generator function for streaming response.
        Handles client disconnects and errors gracefully.
        """
        full_answer = ""
        chunk_count = 0
        t_ai_start = _time.monotonic()
        t_first_chunk = None

        try:
            async for chunk in provider.chat_stream(
                [{"role": item["role"], "content": item["content"]} for item in history],
                context=assistant_seed.get("context") or [],
                citations=citations,
                user_memories=user_memories,
            ):
                chunk_count += 1
                full_answer += chunk

                if t_first_chunk is None:
                    t_first_chunk = _time.monotonic()
                    logger.info("[PERF] First AI chunk arrived: %.3fs (TTFT)", t_first_chunk - t_ai_start)

                # Send SSE event with proper format
                event_data = json.dumps({
                    'chunk': chunk,
                    'done': False
                }, ensure_ascii=False)
                yield f"data: {event_data}\n\n"

            # Stream completed successfully — clean reasoning, then save
            t_ai_done = _time.monotonic()
            logger.info("[PERF] AI streaming done: %.3fs total, %d chunks, %d chars",
                        t_ai_done - t_ai_start, chunk_count, len(full_answer))
            logger.info("[PERF] === END-TO-END: %.3fs ===", t_ai_done - t_start)
            clean_answer = strip_reasoning(full_answer.strip())
            with SessionLocal() as session:
                try:
                    session.add(
                        ChatMessage(
                            session_id=session_id,
                            role="assistant",
                            content=clean_answer,
                            citations=citations,
                            tokens_in=usage.get('prompt_tokens'),
                            tokens_out=usage.get('completion_tokens'),
                            latency_ms=int((t_ai_done - t_start) * 1000),
                        )
                    )
                    # Touch session updated_at so sidebar ordering reflects activity
                    chat_session_obj = session.get(ChatSession, session_id)
                    if chat_session_obj:
                        chat_session_obj.updated_at = func.now()
                    session.commit()
                except Exception as e:
                    logger.error("Failed to save chat message: %s", e, exc_info=True)

            store.append_message(scope_id, session_id, "assistant", clean_answer)

            # Async memory extraction — extract learnable facts from this turn
            try:
                task = asyncio.create_task(
                    memory_service.extract_memories_from_turn(
                        auth.user_id, request.query, clean_answer
                    )
                )
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
            except Exception:
                pass  # Memory extraction is best-effort, never block the response

            # Send final event with session info and citations
            usage = getattr(provider, 'last_usage', {})
            # Estimate cost: Gemini 2.5 Flash pricing
            # Input: $0.075/1M tokens, Output: $0.30/1M tokens
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            estimated_cost_usd = (prompt_tokens * 0.075 + completion_tokens * 0.30) / 1_000_000

            final_data = json.dumps({
                'chunk': '',
                'done': True,
                'session_id': session_id,
                'citations': citations,
                'stats': {
                    'total_ms': int((t_ai_done - t_start) * 1000),
                    'ttft_ms': int((t_first_chunk - t_ai_start) * 1000) if t_first_chunk else None,
                    'chunks': chunk_count,
                    'chars': len(clean_answer),
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': prompt_tokens + completion_tokens,
                    'estimated_cost_usd': round(estimated_cost_usd, 6),
                }
            }, ensure_ascii=False)
            yield f"data: {final_data}\n\n"

            # Security: Don't log actual chat content (PII exposure risk)
            logger.info("Streaming completed: user=%s session=%s chunks=%d chars=%d citations=%d",
                       auth.user_id[:8], session_id[:8], chunk_count, len(full_answer), len(citations))

        except GeneratorExit:
            # Client disconnected - clean up silently
            logger.info("Client disconnected: user=%s session=%s chunks=%d",
                       auth.user_id[:8], session_id[:8], chunk_count)
            raise

        except Exception as e:
            logger.error("AI streaming error after %d chunks: %s", chunk_count, e, exc_info=True)

            # Send user-friendly error message
            error_msg = _build_user_friendly_error(e)
            error_data = json.dumps({
                'chunk': '',
                'done': True,
                'error': error_msg
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        }
    )


@router.post("/chat/sessions")
async def create_chat_session(auth: AuthContext = Depends(get_auth_context)) -> dict[str, object]:
    """Create a new empty chat session."""
    with SessionLocal() as session:
        chat_session = ChatSession(id=uuid4(), user_id=auth.user_id, title="Active chat")
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        return {
            "session_id": str(chat_session.id),
            "title": chat_session.title,
            "created_at": chat_session.created_at.isoformat(),
            "updated_at": chat_session.updated_at.isoformat(),
            "message_count": 0,
        }


@router.get("/chat/sessions")
async def get_chat_sessions(auth: AuthContext = Depends(get_auth_context)) -> list[dict[str, object]]:
    """
    Get all chat sessions for the current user.
    Returns list of sessions with message counts and creation times.
    """
    with SessionLocal() as session:
        rows = (
            session.query(
                ChatSession.id,
                ChatSession.title,
                ChatSession.created_at,
                ChatSession.updated_at,
                func.count(ChatMessage.id).label("message_count"),
            )
            .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
            .filter(ChatSession.user_id == auth.user_id)
            .group_by(ChatSession.id)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )

        return [
            {
                "session_id": str(r.id),
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
                "message_count": r.message_count,
                "title": r.title or "Chat session",
            }
            for r in rows
        ]


@router.get("/chat/messages")
async def get_chat_messages(
    session_id: str,
    limit: int = 20,
    offset: int = 0,
    auth: AuthContext = Depends(get_auth_context),
) -> dict[str, object]:
    """
    Get messages for a specific chat session with pagination.
    Used by frontend to restore conversation after browser refresh.
    Returns messages ordered by creation time (newest first for pagination).
    Default: last 20 messages. Use offset to load older messages.
    """
    try:
        UUID(session_id)
    except ValueError:
        raise http_errors.bad_request("Invalid session ID format")

    # Clamp limit to reasonable range
    limit = max(1, min(limit, 100))

    with SessionLocal() as session:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise http_errors.not_found("Chat session not found")
        if str(chat_session.user_id) != auth.user_id:
            raise http_errors.forbidden("Chat session does not belong to this user")

        # Get total count
        total = (
            session.query(func.count(ChatMessage.id))
            .filter(ChatMessage.session_id == session_id)
            .scalar()
        )

        # Get messages: offset from the END (oldest messages)
        # This way offset=0 returns the newest messages
        effective_offset = max(0, total - offset - limit)
        effective_limit = min(limit, total - offset)

        if effective_limit <= 0:
            return {"messages": [], "total": total, "has_more": False}

        messages = (
            session.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(effective_offset)
            .limit(effective_limit)
            .all()
        )

        has_more = effective_offset > 0

        return {
            "messages": [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "citations": m.citations or [],
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
            "total": total,
            "has_more": has_more,
        }


@router.post("/chat")
async def chat(request: ChatRequest, auth: AuthContext = Depends(get_auth_context)) -> dict[str, object]:
    """
    Non-streaming chat endpoint with fallback support.
    Used when streaming fails or for clients that don't support SSE.

    Returns complete answer with citations in single response.
    """
    # Rate limiting
    if not throttle.allow(
        f"throttle:chat:{auth.user_id}",
        limit=settings.effective_rate_limit(100),
        window_seconds=60,
    ):
        raise http_errors.too_many_requests(
            "Too many chat requests. Please wait a moment before trying again."
        )

    # Validate query input
    _validate_query(request.query)

    scope_id = f"user:{auth.user_id}"
    session_id = request.session_id or store.get_active_session(scope_id) or str(uuid4())
    store.set_active_session(scope_id, session_id)

    # Validate UUID format before DB query
    try:
        UUID(session_id)
    except ValueError:
        raise http_errors.bad_request("Invalid session ID format")

    with SessionLocal() as session:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            chat_session = ChatSession(id=session_id, user_id=auth.user_id, title="Active chat")
            session.add(chat_session)
            session.commit()
        elif str(chat_session.user_id) != auth.user_id:
            raise http_errors.forbidden("Chat session does not belong to this user")

        # Auto-title from first user message
        if chat_session.title == "Active chat":
            chat_session.title = request.query[:80] + ("..." if len(request.query) > 80 else "")
            session.commit()

        store.append_message(scope_id, session_id, "user", request.query)

        # Save user message to PostgreSQL for persistence
        session.add(ChatMessage(session_id=session_id, role="user", content=request.query))
        session.commit()

        # Hydrate Redis from DB only if TTL expired (Redis empty)
        if not store.history_exists(scope_id, session_id):
            db_msgs = session.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at.asc()).all()
            db_dicts = [{"role": m.role, "content": m.content} for m in db_msgs]
        store.hydrate_from_db(scope_id, session_id, db_dicts)

        try:
            # Multi-query expansion for non-streaming endpoint
            queries = [request.query]
            if settings.retrieval_query_expansion_enabled:
                from app.services.retrieval.query_expand import expand_query
                queries = await asyncio.wait_for(
                    expand_query(request.query),
                    timeout=3.0,
                )

            context = retrieve_context(session, queries, limit=20)
            assistant_seed = build_answer(request.query, context)
            history = store.get_history(scope_id, session_id)

            # Deduplicate citations before passing to provider
            raw_citations = assistant_seed.get("citations") or []
            citations = _deduplicate_citations(raw_citations)

            # Load user memories
            user_memories = memory_service.format_memories_for_prompt(auth.user_id)

        except Exception as e:
            logger.error("Error preparing chat context: %s", e, exc_info=True)
            raise http_errors.internal_server_error(
                "Failed to prepare chat context. Please try again."
            ) from None

        try:
            response = await provider.chat(
                [{"role": item["role"], "content": item["content"]} for item in history],
                context=assistant_seed["context"],
                citations=citations,
                user_memories=user_memories,
            )
        except Exception as e:
            logger.error("AI Provider error: %s", e, exc_info=True)

            # Provide user-friendly error message
            error_detail = _build_user_friendly_error(e)
            raise http_errors.service_unavailable(error_detail) from None

        answer = strip_reasoning(response.get("answer") or assistant_seed["answer"])
        citations = response.get("citations") or citations

        try:
            session.add(
                ChatMessage(
                    session_id=chat_session.id,
                    role="assistant",
                    content=answer,
                    citations=citations,
                )
            )
            session.commit()
        except Exception as e:
            logger.error("Failed to save chat message: %s", e, exc_info=True)
            # Continue anyway - user already got the answer

    store.append_message(scope_id, session_id, "assistant", answer)
    return {"session_id": session_id, "answer": answer, "citations": citations}
