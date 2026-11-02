from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base
from app.db.types import tz_datetime

if TYPE_CHECKING:
    from app.db.models.cart_item import CartItemORM
    from app.db.models.conversation import ConversationORM


class CartORM(Base):
    __tablename__ = "carts"

    conversation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversations.conversation_id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(32), default="browsing")
    cart_hash: Mapped[str | None] = mapped_column(String(64))
    confirmation_token: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = tz_datetime(onupdate=utcnow)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    conversation: Mapped["ConversationORM"] = relationship(back_populates="cart")
    items: Mapped[list["CartItemORM"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan"
    )
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
