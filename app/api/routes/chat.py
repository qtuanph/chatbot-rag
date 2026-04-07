from fastapi import APIRouter, Depends

from app.api.deps import get_auth_context
from app.schemas.chat import ChatRequest


router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest, _auth=Depends(get_auth_context)) -> dict[str, object]:
    return {
        "message": "Chat pipeline not implemented yet.",
        "query": request.query,
        "provider": "document-default",
    }
