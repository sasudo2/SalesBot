from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import JsonType, tz_datetime

if TYPE_CHECKING:
    from app.db.models.conversation import ConversationORM


class MessageORM(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("conversation_id", "seq"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversations.conversation_id", ondelete="CASCADE")
    )
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str | None] = mapped_column(Text)
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    tool_call_id: Mapped[str | None] = mapped_column(String(64))
    usage: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    created_at: Mapped[datetime] = tz_datetime()
    conversation: Mapped["ConversationORM"] = relationship(back_populates="messages")
