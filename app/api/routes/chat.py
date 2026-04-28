"""Chat API — streaming chat endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
import time as _time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import AuthContext, get_auth_context, get_chat_service
from app.adapters.ai import build_ai_provider
from app.adapters.ai.google import strip_reasoning
from app.core.config import settings
from app.core import http_errors
from app.schemas.chat import ChatRequest
from app.services.chat.chat_service import ChatService
from app.utils.throttle import RequestThrottle

router = APIRouter(tags=["chat"])
throttle = RequestThrottle()
logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    auth: AuthContext = Depends(get_auth_context),
    service: ChatService = Depends(get_chat_service),
):
    """Streaming chat endpoint — SSE format."""
    if not throttle.allow(f"throttle:chat:{auth.user_id}", limit=settings.effective_rate_limit(100), window_seconds=60):
        raise http_errors.too_many_requests("Too many chat requests. Please wait a moment before trying again.")

    try:
        prep = await service.prepare_chat(
            user_id=auth.user_id,
            query=request.query,
            session_id=request.session_id,
        )
    except ValueError as e:
        raise http_errors.bad_request(str(e)) from None
    except Exception as e:
        logger.error("Error preparing chat context: %s", e, exc_info=True)
        raise http_errors.internal_server_error("Failed to prepare chat context. Please try again.") from None

    provider = build_ai_provider()
    session_id = prep["session_id"]
    history = prep["history"]
    assistant_seed = prep["assistant_seed"]
    citations = prep["citations"]
    user_memories = prep["user_memories"]

    t_start = _time.monotonic()

    async def generate() -> AsyncGenerator[str, None]:
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

                event_data = json.dumps({"chunk": chunk, "done": False}, ensure_ascii=False)
                yield f"data: {event_data}\n\n"

            t_ai_done = _time.monotonic()
            logger.info("[PERF] AI streaming done: %d chunks, %d chars", chunk_count, len(full_answer))
            clean_answer = strip_reasoning(full_answer.strip())
            usage = getattr(provider, "last_usage", {})

            service.save_assistant_message(
                session_id=session_id,
                user_id=auth.user_id,
                content=clean_answer,
                citations=citations,
                tokens_in=usage.get("prompt_tokens"),
                tokens_out=usage.get("completion_tokens"),
                latency_ms=int((t_ai_done - t_start) * 1000),
                model_used=getattr(provider, "model_name", settings.google_model),
            )

            # Async memory extraction
            try:
                task = asyncio.create_task(service.extract_memories(auth.user_id, request.query, clean_answer))
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)
            except Exception as e:
                logger.debug("Memory extraction failed (best-effort): %s", e)

            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            estimated_cost_usd = ChatService.compute_cost(prompt_tokens, completion_tokens)

            final_data = json.dumps(
                {
                    "chunk": "",
                    "done": True,
                    "session_id": session_id,
                    "citations": citations,
                    "stats": {
                        "total_ms": int((t_ai_done - t_start) * 1000),
                        "ttft_ms": int((t_first_chunk - t_ai_start) * 1000) if t_first_chunk else None,
                        "chunks": chunk_count,
                        "chars": len(clean_answer),
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "estimated_cost_usd": round(estimated_cost_usd, 6),
                    },
                },
                ensure_ascii=False,
            )
            yield f"data: {final_data}\n\n"

            logger.info(
                "Streaming completed: user=%s session=%s chunks=%d", auth.user_id[:8], session_id[:8], chunk_count
            )

        except GeneratorExit:
            logger.info("Client disconnected: user=%s session=%s", auth.user_id[:8], session_id[:8])
            raise
        except Exception as e:
            logger.error("AI streaming error after %d chunks: %s", chunk_count, e, exc_info=True)
            error_msg = ChatService.build_user_friendly_error(e)
            error_data = json.dumps({"chunk": "", "done": True, "error": error_msg}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/sessions")
async def create_chat_session(
    auth: AuthContext = Depends(get_auth_context), service: ChatService = Depends(get_chat_service)
) -> dict:
    return service.create_session(user_id=auth.user_id)


@router.get("/chat/sessions")
async def get_chat_sessions(
    auth: AuthContext = Depends(get_auth_context), service: ChatService = Depends(get_chat_service)
) -> list[dict]:
    return service.list_sessions(auth.user_id)


@router.get("/chat/messages")
async def get_chat_messages(
    session_id: str,
    limit: int = 20,
    offset: int = 0,
    auth: AuthContext = Depends(get_auth_context),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    try:
        return service.list_messages(session_id=session_id, user_id=auth.user_id, limit=limit, offset=offset)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise http_errors.not_found(msg) from None
        if "not belong" in msg:
            raise http_errors.forbidden(msg) from None
        raise http_errors.bad_request(msg) from None
