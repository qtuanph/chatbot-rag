"""WebSocket chat endpoint for real-time streaming."""

from __future__ import annotations

import json
import logging
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.core.config import settings
from app.api.deps import AuthContext, get_chat_service, get_rate_limiter
from app.modules.chat.services import ChatService
from app.utils.rate_limiter import RateLimiter

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/chat/stream")
async def chat_stream_websocket(
    websocket: WebSocket,
    service: ChatService = Depends(get_chat_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    """WebSocket endpoint for chat streaming."""
    await websocket.accept()
    user_id = None

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            query = msg.get("query", "")
            session_id = msg.get("session_id") or None
            thinking_mode = msg.get("thinking_mode", False)

            if not query or not query.strip():
                await websocket.send_json({"error": "Query cannot be empty", "done": True})
                continue

            # Quick check if 9Router has any models configured
            try:
                headers = {}
                if settings.ai_proxy_api_key:
                    headers["Authorization"] = f"Bearer {settings.ai_proxy_api_key}"
                async with httpx.AsyncClient(timeout=3.0) as client:
                    mr = await client.get(
                        f"{settings.ai_proxy_url.rstrip('/')}/v1/models",
                        headers=headers,
                    )
                    if mr.status_code != 200 or not mr.json().get("data"):
                        await websocket.send_json(
                            {
                                "error": "Chưa kết nối AI provider. Vào Admin → Kết nối để thêm provider.",
                                "done": True,
                            }
                        )
                        continue
            except Exception:
                await websocket.send_json(
                    {
                        "error": "Chưa kết nối AI provider. Vào Admin → Kết nối để thêm provider.",
                        "done": True,
                    }
                )
                continue

            auth = AuthContext(user_id=msg.get("user_id", "anonymous"), role="user", token_id="ws")
            user_id = auth.user_id

            if not await rate_limiter.is_allowed(auth.user_id, limit=30, window_ms=60000):
                await websocket.send_json({"error": "Too many requests. Please wait.", "done": True})
                continue

            prep = await service.prepare_chat(user_id=auth.user_id, query=query, session_id=session_id)

            async for chunk in service.stream_chat_events(
                user_id=auth.user_id, query=query, prepared_chat=prep, thinking_mode=thinking_mode
            ):
                if isinstance(chunk, str) and chunk.startswith("data: "):
                    parsed = json.loads(chunk[6:])
                    await websocket.send_json(parsed)
                elif isinstance(chunk, dict):
                    await websocket.send_json(chunk)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user=%s", user_id)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        try:
            await websocket.send_json({"error": str(e), "done": True})
        except Exception:
            pass
