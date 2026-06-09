from __future__ import annotations

import json
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import get_tenant_api_context, TenantApiContext
from app.core import http_errors
from app.db.session import get_async_session
from app.modules.documents.repositories.section_repository import SectionRepository
from app.modules.inference.schemas import ChatCompletionsRequest
from app.modules.inference.service import PublicInferenceService
from app.modules.tenants.repository import TenantRepository

router = APIRouter(prefix="/public/v1", tags=["public-inference"])


def get_public_inference_service(session=Depends(get_async_session)) -> PublicInferenceService:
    return PublicInferenceService(TenantRepository(session), SectionRepository(session))


@router.get("/health")
async def public_health() -> dict[str, str]:
    return {"status": "up"}


@router.get("/models")
async def list_public_models(api_context: TenantApiContext = Depends(get_tenant_api_context)) -> dict:
    return {
        "object": "list",
        "data": [
            {
                "id": "chatbot-rag",
                "object": "model",
                "owned_by": api_context.tenant_id,
            }
        ],
    }


@router.post("/chat/completions")
async def create_chat_completion(
    payload: ChatCompletionsRequest,
    api_context: TenantApiContext = Depends(get_tenant_api_context),
    service: PublicInferenceService = Depends(get_public_inference_service),
):
    messages = [message.model_dump() for message in payload.messages]
    try:
        if payload.stream:
            return StreamingResponse(
                service.stream_complete(
                    tenant_id=api_context.tenant_id,
                    messages=messages,
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
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            user_id=None,
        )
        return JSONResponse(
            {
                "id": f"chatcmpl-{api_context.request_id}",
                "object": "chat.completion",
                "created": 0,
                "model": result.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": result.content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": result.usage,
                "citations": result.citations,
            }
        )
    except ValueError as exc:
        raise http_errors.bad_request(str(exc)) from None
    except Exception as exc:
        error_payload = {"error": {"message": str(exc), "type": "server_error"}}
        return JSONResponse(status_code=500, content=json.loads(json.dumps(error_payload)))
