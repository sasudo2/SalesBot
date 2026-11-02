from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JsonType, tz_datetime


class CartEventORM(Base):
    __tablename__ = "cart_events"
    __table_args__ = (
        Index("ix_cart_events_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversations.conversation_id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JsonType)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = tz_datetime()
