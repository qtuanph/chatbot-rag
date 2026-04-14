from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

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


@router.post("/chat")
async def chat(request: ChatRequest, auth: AuthContext = Depends(get_auth_context)) -> dict[str, object]:
    if not throttle.allow(f"throttle:chat:{auth.user_id}", limit=30, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many chat requests")

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

        context = retrieve_context(session, request.query, limit=20)
        assistant_seed = build_answer(request.query, context)
        history = store.get_history(scope_id, session_id)
        try:
            response = await provider.chat(
                [{"role": item["role"], "content": item["content"]} for item in history],
                context=assistant_seed["context"],
                citations=assistant_seed["citations"],
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("AI Provider error: %s", e, exc_info=True)
            raise HTTPException(status_code=503, detail="Lỗi kết nối với AI Model. Có thể từ khóa bị chặn hoặc hết lượt gọi cấp phép. Vui lòng thử lại sau.") from None

        answer = response.get("answer") or assistant_seed["answer"]
        citations = response.get("citations") or assistant_seed["citations"]

        session.add(
            ChatMessage(
                session_id=chat_session.id,
                role="assistant",
                content=answer,
                citations=citations,
            )
        )
        session.commit()

    store.append_message(scope_id, session_id, "assistant", answer)
    return {"session_id": session_id, "answer": answer, "citations": citations}
