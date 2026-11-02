from typing import Any

from pydantic import BaseModel, Field

from app.domain.models import ToolCall, Usage


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    provider: str = ""
    model: str = ""
