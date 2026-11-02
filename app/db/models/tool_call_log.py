from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JsonType, tz_datetime


class ToolCallLogORM(Base):
    __tablename__ = "tool_call_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversations.conversation_id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    tool_name: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict[str, Any]] = mapped_column(JsonType)
    status: Mapped[str] = mapped_column(String(16))
    error_code: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = tz_datetime()
