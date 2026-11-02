from typing import Any

from pydantic import BaseModel

from app.llm.types import ToolSpec
from app.tools import (
    cart_tools,
    catalog,
    customer_tools,
    handoff_tools,
    knowledge_tools,
    order_tools,
)
from app.tools.args import (
    AddToCartArgs,
    GetProductArgs,
    HandoffArgs,
    NoArgs,
    PlaceOrderArgs,
    RemoveFromCartArgs,
    SearchKnowledgeArgs,
    SearchProductsArgs,
    SetCustomerInfoArgs,
    UpdateCartItemArgs,
)
from app.tools.registry import Handler, ToolRegistry


def _strip_titles(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_titles(item) for key, item in value.items() if key != "title"}
    if isinstance(value, list):
        return [_strip_titles(item) for item in value]
    return value


def build_tool_registry() -> ToolRegistry:
    definitions: list[tuple[str, str, type[BaseModel], Handler]] = [
        (
            "search_products",
            "Search the shop catalogue by free text (name, nickname, tag, description). "
            "Returns up to `limit` products with price, currency and available stock. "
            "Always call this before quoting any price or availability.",
            SearchProductsArgs,
            catalog.tool_search_products,
        ),
        (
            "get_product",
            "Get one product by id with current price and available stock.",
            GetProductArgs,
            catalog.tool_get_product,
        ),
        (
            "add_to_cart",
            "Add a product to the customer's cart. Fails if the quantity exceeds available stock.",
            AddToCartArgs,
            cart_tools.tool_add_to_cart,
        ),
        (
            "update_cart_item",
            "Set the quantity of a product already in the cart. Quantity 0 removes it.",
            UpdateCartItemArgs,
            cart_tools.tool_update_cart_item,
        ),
        (
            "remove_from_cart",
            "Remove a product from the cart.",
            RemoveFromCartArgs,
            cart_tools.tool_remove_from_cart,
        ),
        (
            "view_cart",
            "Show the current cart with line totals and total.",
            NoArgs,
            cart_tools.tool_view_cart,
        ),
        (
            "set_customer_info",
            "Save the customer's name and phone number. "
            "Required before requesting order confirmation.",
            SetCustomerInfoArgs,
            customer_tools.tool_set_customer_info,
        ),
        (
            "request_order_confirmation",
            "Lock the cart, reserve stock and return a summary plus a confirmation_token. "
            "Then ask the customer to confirm. Do not place the order in the same turn.",
            NoArgs,
            order_tools.tool_request_confirmation,
        ),
        (
            "place_order",
            "Place the order using the confirmation_token, only after the customer explicitly "
            "confirmed in their latest message.",
            PlaceOrderArgs,
            order_tools.tool_place_order,
        ),
        (
            "cancel_cart",
            "Empty the cart and release any reserved stock.",
            NoArgs,
            cart_tools.tool_cancel_cart,
        ),
        (
            "search_knowledge",
            "Search shop policies, FAQs and catalogue notes "
            "(delivery, returns, payment, opening hours). "
            "Use before answering policy questions.",
            SearchKnowledgeArgs,
            knowledge_tools.tool_search_knowledge,
        ),
        (
            "handoff_to_human",
            "Hand the conversation to a human agent. Use for complaints, refunds, payment problems "
            "or when the customer asks for a person.",
            HandoffArgs,
            handoff_tools.tool_handoff_to_human,
        ),
    ]
    registry = ToolRegistry()
    for name, description, model, handler in definitions:
        registry.register(
            ToolSpec(
                name=name,
                description=description,
                parameters=_strip_titles(model.model_json_schema()),
            ),
            model,
            handler,
        )
    return registry
