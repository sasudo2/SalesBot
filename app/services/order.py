from sqlalchemy.orm import Session

from app.domain.enums import CartEventType
from app.domain.errors import InvalidStateError, TokenMismatchError
from app.domain.models import Cart, Conversation, Order, OrderItem
from app.repo.cart_event import record_cart_event
from app.repo.order import get_order_by_idempotency_key, insert_order
from app.services.cart import assert_confirmable, reset_cart
from app.services.inventory import commit_stock


def build_order(conversation: Conversation, cart: Cart, currency: str = "NPR") -> Order:
    if not conversation.customer_name or not conversation.customer_phone:
        raise InvalidStateError("Customer name and phone are required")
    return Order(
        conversation_id=conversation.conversation_id,
        customer_name=conversation.customer_name,
        customer_phone=conversation.customer_phone,
        items=[OrderItem(**item.model_dump()) for item in cart.items],
        total=cart.total,
        currency=currency,
        confirmation_token=cart.confirmation_token,
    )


def place_order_from_cart(
    db: Session, conversation: Conversation, token: str, currency: str = "NPR"
) -> Order:
    existing = get_order_by_idempotency_key(db, token)
    if existing is not None:
        if existing.conversation_id != conversation.conversation_id:
            raise TokenMismatchError("Confirmation token does not match this conversation")
        return existing
    assert_confirmable(conversation, token)
    cart = conversation.ensure_cart()
    order = build_order(conversation, cart, currency)
    commit_stock(db, cart)
    inserted = insert_order(db, order)
    record_cart_event(db, conversation.conversation_id, CartEventType.order_placed, cart)
    reset_cart(cart)
    return inserted
