from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base
from app.db.types import tz_datetime

if TYPE_CHECKING:
    from app.db.models.cart import CartORM
    from app.db.models.message import MessageORM


class ConversationORM(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    channel: Mapped[str] = mapped_column(String(16), default="web")
    customer_name: Mapped[str | None] = mapped_column(String(100))
    customer_phone: Mapped[str | None] = mapped_column(String(20), index=True)
    handoff: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str | None] = mapped_column(Text)
    summarized_upto: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    last_updated: Mapped[datetime] = tz_datetime(onupdate=utcnow)
    messages: Mapped[list["MessageORM"]] = relationship(
        back_populates="conversation", order_by="MessageORM.seq", cascade="all, delete-orphan"
    )
    cart: Mapped[Optional["CartORM"]] = relationship(
        back_populates="conversation", uselist=False, cascade="all, delete-orphan"
    )
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
