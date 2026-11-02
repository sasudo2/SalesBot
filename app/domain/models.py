from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.core.time import utcnow
from app.domain.enums import CartStatus, Channel, KnowledgeSource, MessageRole, OrderStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class Message(ORMModel):
    role: MessageRole
    content: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage | None = None


class CartItem(ORMModel):
    product_id: str
    name: str
    quantity: int
    unit_price: Decimal

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


class CartSummary(BaseModel):
    status: CartStatus
    items: list[CartItem]
    total: Decimal


class Cart(ORMModel):
    conversation_id: UUID
    status: CartStatus = CartStatus.browsing
    items: list[CartItem] = Field(default_factory=list)
    cart_hash: str | None = None
    confirmation_token: str | None = None
    updated_at: datetime = Field(default_factory=utcnow)

    @property
    def total(self) -> Decimal:
        return sum((i.line_total for i in self.items), Decimal("0.00"))

    def to_summary(self) -> CartSummary:
        return CartSummary(status=self.status, items=list(self.items), total=self.total)


class Conversation(ORMModel):
    conversation_id: UUID = Field(default_factory=uuid4)
    channel: Channel = Channel.web
    customer_name: str | None = None
    customer_phone: str | None = None
    handoff: bool = False
    summary: str | None = None
    summarized_upto: int = 0
    messages: list[Message] = Field(default_factory=list)
    cart: Cart | None = None
    version: int = 1
    last_updated: datetime = Field(default_factory=utcnow)

    @property
    def last_user_message(self) -> Message | None:
        return next((m for m in reversed(self.messages) if m.role == MessageRole.user), None)

    def ensure_cart(self) -> Cart:
        if self.cart is None:
            self.cart = Cart(conversation_id=self.conversation_id)
        return self.cart


class OrderItem(ORMModel):
    product_id: str
    name: str
    quantity: int
    unit_price: Decimal


class Order(ORMModel):
    order_id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    customer_name: str
    customer_phone: str
    status: OrderStatus = OrderStatus.pending
    items: list[OrderItem]
    total: Decimal
    currency: str = "NPR"
    confirmation_token: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Product(ORMModel):
    id: str
    sku: str
    name: str
    description: str = ""
    price: Decimal
    currency: str = "NPR"
    stock_on_hand: int = 0
    reserved: int = 0
    active: bool = True
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    embedding_hash: str | None = None

    @property
    def available(self) -> int:
        return self.stock_on_hand - self.reserved


class KnowledgeChunk(ORMModel):
    id: int | None = None
    source: KnowledgeSource
    title: str
    text: str
    embedding: list[float] | None = None
    version: int = 1
    updated_at: datetime = Field(default_factory=utcnow)


class ProductHit(BaseModel):
    product: Product
    score: float
    available: int


class KnowledgeHit(BaseModel):
    chunk: KnowledgeChunk
    score: float
