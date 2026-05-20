from pydantic import BaseModel, Field


class MessageFeedbackRequest(BaseModel):
    """Request to update message feedback."""

    feedback: int = Field(ge=-1, le=1, description="Feedback value: 1 (like), -1 (dislike), 0 (none)")


class MessageFeedbackResponse(BaseModel):
    """Response after updating feedback."""

    message_id: str
    feedback: int
    status: str = "updated"
