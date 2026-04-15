from __future__ import annotations

import json
import logging
from uuid import UUID, uuid4
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import AuthContext, get_auth_context
from app.adapters.ai import build_ai_provider
from app.db.session import SessionLocal
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import ChatRequest
from app.services.chat_store import ChatStore
from app.services.rag import build_answer, retrieve_context
from app.services.throttle import RequestThrottle


router = APIRouter(tags=["chat"])
store = ChatStore()
provider = build_ai_provider()
throttle = RequestThrottle()
logger = logging.getLogger(__name__)


def _deduplicate_citations(citations: list[dict]) -> list[dict]:
    """
    Deduplicate citations by document_id and node_id, keeping the most relevant one.
    Sorts by index (relevance order from retrieval).

    Args:
        citations: List of citation dicts with document_id, node_id, index, etc.

    Returns:
        Deduplicated and sorted citations list (max 10)
    """
    if not citations:
        return []

    # Use dict to dedupe by document_id + node_id combo
    seen: dict[tuple[str | None, str | None], dict] = {}
    for citation in citations:
        key = (citation.get("document_id"), citation.get("node_id"))
        if key not in seen:
            seen[key] = citation
        else:
            # Keep the one with lower index (more relevant)
            # Note: index is always present in build_answer() but we use defensive fallback
            current_index = citation.get("index", 999)
            existing_index = seen[key].get("index", 999)
            if current_index < existing_index:
                seen[key] = citation

    # Sort by index and limit to top 10
    deduped = list(seen.values())
    deduped.sort(key=lambda x: x.get("index", 999))

    # Ensure all citations have required fields
    for citation in deduped:
        citation.setdefault("title", "Tài liệu")
        citation.setdefault("heading", "Nội dung")
        citation.setdefault("page_range", None)

    return deduped[:10]


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
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if len(query) > 5000:
        raise HTTPException(status_code=400, detail="Query too long (max 5000 characters)")

    # Check for potential injection patterns (basic sanitization)
    dangerous_patterns = ["<script>", "javascript:", "onerror=", "onload="]
    query_lower = query.lower()
    if any(pattern in query_lower for pattern in dangerous_patterns):
        raise HTTPException(status_code=400, detail="Query contains invalid characters")


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
    if not throttle.allow(f"throttle:chat:{auth.user_id}", limit=30, window_seconds=60):
        raise HTTPException(
            status_code=429,
            detail="Too many chat requests. Please wait a moment before trying again."
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
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    with SessionLocal() as session:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            chat_session = ChatSession(id=session_id, user_id=auth.user_id, title="Active chat")
            session.add(chat_session)
            session.commit()
        elif str(chat_session.user_id) != auth.user_id:
            raise HTTPException(status_code=403, detail="Chat session does not belong to this user")

        store.append_message(scope_id, session_id, "user", request.query)

        try:
            context = retrieve_context(session, request.query, limit=20)
            assistant_seed = build_answer(request.query, context)
            history = store.get_history(scope_id, session_id)

            # Deduplicate and clean citations
            raw_citations = assistant_seed.get("citations") or []
            citations = _deduplicate_citations(raw_citations)

        except Exception as e:
            logger.error("Error preparing chat context: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to prepare chat context. Please try again."
            ) from None

    async def generate() -> AsyncGenerator[str, None]:
        """
        Generator function for streaming response.
        Handles client disconnects and errors gracefully.
        """
        full_answer = ""
        chunk_count = 0

        try:
            async for chunk in provider.chat_stream(
                [{"role": item["role"], "content": item["content"]} for item in history],
                context=assistant_seed.get("context") or [],
                citations=citations,
            ):
                chunk_count += 1
                full_answer += chunk

                # Send SSE event with proper format
                # Note: double newline is required for SSE
                event_data = json.dumps({
                    'chunk': chunk,
                    'done': False
                }, ensure_ascii=False)
                yield f"data: {event_data}\n\n"

            # Stream completed successfully - save to database
            with SessionLocal() as session:
                try:
                    session.add(
                        ChatMessage(
                            session_id=chat_session.id,
                            role="assistant",
                            content=full_answer,
                            citations=citations,
                        )
                    )
                    session.commit()
                except Exception as e:
                    logger.error("Failed to save chat message: %s", e, exc_info=True)
                    # Continue anyway - user already got the answer

            store.append_message(scope_id, session_id, "assistant", full_answer)

            # Send final event with session info and citations
            final_data = json.dumps({
                'chunk': '',
                'done': True,
                'session_id': session_id,
                'citations': citations
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


@router.get("/chat/sessions")
async def get_chat_sessions(auth: AuthContext = Depends(get_auth_context)) -> list[dict[str, object]]:
    """
    Get all chat sessions for the current user.
    Returns list of sessions with message counts and creation times.
    """
    with SessionLocal() as session:
        sessions = (
            session.query(ChatSession)
            .filter(ChatSession.user_id == auth.user_id)
            .order_by(ChatSession.created_at.desc())
            .all()
        )

        result = []
        for s in sessions:
            # Count messages for each session
            message_count = (
                session.query(ChatMessage)
                .filter(ChatMessage.session_id == s.id)
                .count()
            )

            result.append({
                "session_id": str(s.id),
                "created_at": s.created_at.isoformat(),
                "message_count": message_count,
                "title": s.title or "Chat session",
            })

        return result


@router.post("/chat")
async def chat(request: ChatRequest, auth: AuthContext = Depends(get_auth_context)) -> dict[str, object]:
    """
    Non-streaming chat endpoint with fallback support.
    Used when streaming fails or for clients that don't support SSE.

    Returns complete answer with citations in single response.
    """
    # Rate limiting
    if not throttle.allow(f"throttle:chat:{auth.user_id}", limit=30, window_seconds=60):
        raise HTTPException(
            status_code=429,
            detail="Too many chat requests. Please wait a moment before trying again."
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
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    with SessionLocal() as session:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            chat_session = ChatSession(id=session_id, user_id=auth.user_id, title="Active chat")
            session.add(chat_session)
            session.commit()
        elif str(chat_session.user_id) != auth.user_id:
            raise HTTPException(status_code=403, detail="Chat session does not belong to this user")

        store.append_message(scope_id, session_id, "user", request.query)

        try:
            context = retrieve_context(session, request.query, limit=20)
            assistant_seed = build_answer(request.query, context)
            history = store.get_history(scope_id, session_id)

            # Deduplicate citations before passing to provider
            raw_citations = assistant_seed.get("citations") or []
            citations = _deduplicate_citations(raw_citations)

        except Exception as e:
            logger.error("Error preparing chat context: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Failed to prepare chat context. Please try again."
            ) from None

        try:
            response = await provider.chat(
                [{"role": item["role"], "content": item["content"]} for item in history],
                context=assistant_seed["context"],
                citations=citations,
            )
        except Exception as e:
            logger.error("AI Provider error: %s", e, exc_info=True)

            # Provide user-friendly error message
            error_detail = _build_user_friendly_error(e)
            raise HTTPException(status_code=503, detail=error_detail) from None

        answer = response.get("answer") or assistant_seed["answer"]
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
