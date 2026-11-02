from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import KnowledgeSource


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(_Args):
    """Arguments for a tool without parameters."""


class SearchProductsArgs(_Args):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=5, ge=1, le=10)


class GetProductArgs(_Args):
    product_id: str


class AddToCartArgs(_Args):
    product_id: str
    quantity: int = Field(ge=1, le=99)


class UpdateCartItemArgs(_Args):
    product_id: str
    quantity: int = Field(ge=0, le=99)


class RemoveFromCartArgs(_Args):
    product_id: str


class PlaceOrderArgs(_Args):
    confirmation_token: str


class SearchKnowledgeArgs(_Args):
    query: str = Field(min_length=1, max_length=300)
    source: KnowledgeSource | None = None
    limit: int = Field(default=3, ge=1, le=5)


class SetCustomerInfoArgs(_Args):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=7, max_length=20)


class HandoffArgs(_Args):
    reason: str = Field(min_length=1, max_length=300)
