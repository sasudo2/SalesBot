from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JsonType


class ProductORM(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock_on_hand >= 0", name="stock_nonnegative"),
        CheckConstraint("reserved >= 0", name="reserved_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="NPR")
    stock_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    aliases: Mapped[list[str]] = mapped_column(JsonType, default=list)
    tags: Mapped[list[str]] = mapped_column(JsonType, default=list)
    embedding: Mapped[list[float] | None] = mapped_column(JsonType)
    embedding_hash: Mapped[str | None] = mapped_column(String(64))
