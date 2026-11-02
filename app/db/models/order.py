from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import tz_datetime

if TYPE_CHECKING:
    from app.db.models.order_item import OrderItemORM


class OrderORM(Base):
    __tablename__ = "orders"

    order_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversations.conversation_id"), index=True
    )
    customer_name: Mapped[str] = mapped_column(String(100))
    customer_phone: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="NPR")
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = tz_datetime()
    items: Mapped[list["OrderItemORM"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
