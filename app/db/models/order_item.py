from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.order import OrderORM


class OrderItemORM(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("orders.order_id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    order: Mapped["OrderORM"] = relationship(back_populates="items")
