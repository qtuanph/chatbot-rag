from fastapi import APIRouter

from app.schemas.chat import ChatRequest


router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest) -> dict[str, object]:
    return {
        "message": "Chat pipeline not implemented yet.",
        "query": request.query,
        "provider": "document-default",
    }
