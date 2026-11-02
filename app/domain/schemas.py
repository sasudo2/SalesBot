from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import Channel
from app.domain.models import CartSummary


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    conversation_id: UUID
    query: str = Field(min_length=1, max_length=2000)
    channel: Channel = Channel.web


class ChatResponse(BaseModel):
    conversation_id: UUID
    reply: str
    handoff: bool = False
    cart: CartSummary | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    db: bool
