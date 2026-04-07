from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, get_auth_context
from app.adapters.ai import LocalAIProvider
from app.db.session import SessionLocal
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import ChatRequest
from app.services.chat_store import ChatStore
from app.services.rag import build_answer, retrieve_context


router = APIRouter(tags=["chat"])
store = ChatStore()
provider = LocalAIProvider()


@router.post("/chat")
async def chat(request: ChatRequest, auth: AuthContext = Depends(get_auth_context)) -> dict[str, object]:
    project_id = "project"
    session_id = request.session_id or store.get_active_session(project_id) or str(uuid4())
    store.set_active_session(project_id, session_id)

    with SessionLocal() as session:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            chat_session = ChatSession(id=session_id, title="Active chat")
            session.add(chat_session)
            session.commit()

        store.append_message(project_id, session_id, "user", request.query)

        context = retrieve_context(session, request.query, limit=5)
        assistant_seed = build_answer(request.query, context)
        history = store.get_history(project_id, session_id)
        response = await provider.chat(
            [{"role": item["role"], "content": item["content"]} for item in history],
            context=assistant_seed["context"],
            citations=assistant_seed["citations"],
        )

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

    store.append_message(project_id, session_id, "assistant", answer)
    return {"session_id": session_id, "answer": answer, "citations": citations}
