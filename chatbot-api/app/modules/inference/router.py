from __future__ import annotations

import time
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from app.modules.tenants.deps import get_tenant_api_context
from app.modules.tenants.context import TenantApiContext
from app.core import http_errors
from app.core.deps import get_semantic_cache
from app.db.session import get_async_session
from app.modules.documents.repositories.section_repository import SectionRepository
from app.modules.inference.schemas import ChatCompletionsRequest
from app.modules.inference.service import PublicInferenceService
from app.modules.tenants.repository import TenantRepository

router = APIRouter(prefix="", tags=["public-inference"])


def get_public_inference_service(
    session=Depends(get_async_session), semantic_cache=Depends(get_semantic_cache)
) -> PublicInferenceService:
    return PublicInferenceService(TenantRepository(session), SectionRepository(session), semantic_cache=semantic_cache)


# ── OpenAI-compatible endpoints ────────────────────────────────────


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "up"}


@router.get("/models")
async def list_models(
    api_context: TenantApiContext = Depends(get_tenant_api_context),
) -> dict:
    return {
        "object": "list",
        "data": [
            {
                "id": "chatbot-rag",
                "object": "model",
                "created": int(time.time()),
                "owned_by": api_context.tenant_id,
            }
        ],
    }


@router.post("/chat/completions")
async def chat_completions(
    payload: ChatCompletionsRequest,
    api_context: TenantApiContext = Depends(get_tenant_api_context),
    service: PublicInferenceService = Depends(get_public_inference_service),
):
    messages = [m.model_dump() for m in payload.messages]
    try:
        if payload.stream:
            return StreamingResponse(
                service.stream_complete(
                    tenant_id=api_context.tenant_id,
                    messages=messages,
                    thinking_mode=payload.thinking_mode,
                    temperature=payload.temperature,
                    max_tokens=payload.max_tokens,
                    user_id=None,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        result = await service.complete(
            tenant_id=api_context.tenant_id,
            messages=messages,
            thinking_mode=payload.thinking_mode,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            user_id=None,
        )
        return {
            "id": f"chatcmpl-{api_context.request_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": result.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result.content},
                    "finish_reason": "stop",
                }
            ],
            "usage": result.usage,
        }
    except ValueError as exc:
        raise http_errors.bad_request(str(exc)) from None
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(exc),
                    "type": "server_error",
                    "code": "internal_error",
                }
            },
        )
