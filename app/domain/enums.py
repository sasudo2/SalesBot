from enum import StrEnum


class Channel(StrEnum):
    web = "web"
    whatsapp = "whatsapp"
    messenger = "messenger"
    viber = "viber"


class MessageRole(StrEnum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class CartStatus(StrEnum):
    browsing = "browsing"
    awaiting_confirmation = "awaiting_confirmation"


class OrderStatus(StrEnum):
    pending = "pending"
    paid = "paid"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    refunded = "refunded"


class CartEventType(StrEnum):
    item_added = "item_added"
    item_updated = "item_updated"
    item_removed = "item_removed"
    confirmation_request = "confirmation_request"
    order_placed = "order_placed"
    cart_cancelled = "cart_cancelled"
    cart_expired = "cart_expired"


class KnowledgeSource(StrEnum):
    policy = "policy"
    faq = "faq"
    catalogue = "catalogue"


class ToolErrorCode(StrEnum):
    not_found = "not_found"
    out_of_stock = "out_of_stock"
    invalid_args = "invalid_args"
    invalid_state = "invalid_state"
    cart_changed = "cart_changed"
    token_mismatch = "token_mismatch"
    unknown_tool = "unknown_tool"
    provider_error = "provider_error"
    conflict = "conflict"
    internal_error = "internal_error"
