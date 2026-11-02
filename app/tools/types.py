from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import ToolErrorCode


class ToolResult(BaseModel):
    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: ToolErrorCode | None = None
    message: str | None = None
