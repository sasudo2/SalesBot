from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.time import utcnow
from app.db.models import CartEventORM, OrderORM
from app.domain.enums import CartStatus, MessageRole
from app.domain.errors import (
    CartChangedError,
    InvalidStateError,
    NotFoundError,
    OutOfStockError,
    TokenMismatchError,
    ValidationAppError,
)
from app.domain.models import Cart, CartItem, Conversation, Message
from app.repo.conversation import create_conversation, save_conversation
from app.repo.order import insert_order
from app.repo.product import get_product_by_id
from app.services.cart import (
    assert_confirmable,
    begin_confirmation,
    cart_add_item,
    cart_remove_item,
    cart_update_item,
    compute_cart_hash,
    reset_cart,
)
from app.services.inventory import commit_stock, release_stock, reserve_stock
from app.services.jobs import expire_stale_carts
from app.services.order import build_order, place_order_from_cart


def test_cart_service(seed_products):
    p = seed_products[0]
    cart = Cart(conversation_id=uuid4())
    with pytest.raises(ValidationAppError):
        cart_add_item(cart, p, 0)
    cart_add_item(cart, p, 2)
    p.price = Decimal("130.00")
    cart_add_item(cart, p, 1)
    assert len(cart.items) == 1 and cart.items[0].quantity == 3
    assert cart.items[0].unit_price == p.price
    with pytest.raises(OutOfStockError):
        cart_add_item(cart, p, 99)
    with pytest.raises(NotFoundError):
        cart_update_item(cart, "missing", 1)
    with pytest.raises(ValidationAppError):
        cart_update_item(cart, p.id, -1)
    with pytest.raises(OutOfStockError):
        cart_update_item(cart, p.id, 4)
    cart_update_item(cart, p.id, 4, p)
    begin_confirmation(cart, "Sita", "+9779841234567")
    cart_update_item(cart, p.id, 2)
    assert cart.status == CartStatus.browsing and cart.confirmation_token is None
    begin_confirmation(cart, "Sita", "+9779841234567")
    cart_remove_item(cart, p.id)
    assert not cart.items and cart.cart_hash is None
    with pytest.raises(NotFoundError):
        cart_remove_item(cart, p.id)
    cart_add_item(cart, p, 1)
    cart_update_item(cart, p.id, 0)
    assert not cart.items
    assert reset_cart(cart).items == []


def test_cart_hash_and_confirmation(seed_products):
    c = Conversation(customer_name="Sita", customer_phone="+9779841234567")
    with pytest.raises(InvalidStateError):
        assert_confirmable(c, "x")
    cart = c.ensure_cart()
    with pytest.raises(InvalidStateError, match="empty"):
        begin_confirmation(cart, None, None)
    cart_add_item(cart, seed_products[0], 1)
    with pytest.raises(InvalidStateError, match="Customer"):
        begin_confirmation(cart, None, None)
    with pytest.raises(InvalidStateError, match="awaiting"):
        assert_confirmable(c, "x")
    begin_confirmation(cart, c.customer_name, c.customer_phone)
    token = cart.confirmation_token
    with pytest.raises(TokenMismatchError):
        assert_confirmable(c, "wrong")
    with pytest.raises(InvalidStateError, match="new message"):
        assert_confirmable(c, token)
    c.messages.append(Message(role=MessageRole.user, created_at=cart.updated_at))
    with pytest.raises(InvalidStateError):
        assert_confirmable(c, token)
    c.messages[-1].created_at += timedelta(seconds=1)
    assert_confirmable(c, token)
    original = cart.cart_hash
    for field, value in [("quantity", 2), ("unit_price", Decimal("9.00"))]:
        changed = cart.model_copy(deep=True)
        setattr(changed.items[0], field, value)
        assert compute_cart_hash(changed, c.customer_name, c.customer_phone) != original
    assert compute_cart_hash(cart, "Other", c.customer_phone) != original
    c.customer_phone = "+9779741234567"
    with pytest.raises(CartChangedError):
        assert_confirmable(c, token)


def test_inventory(db, seed_products):
    cart = Cart(conversation_id=uuid4())
    cart_add_item(cart, seed_products[0], 2)
    reserve_stock(db, cart)
    assert get_product_by_id(db, "chiura").reserved == 2
    release_stock(db, cart)
    release_stock(db, cart)
    assert get_product_by_id(db, "chiura").reserved == 0
    with pytest.raises(OutOfStockError):
        commit_stock(db, cart)
    cart.items.append(CartItem(product_id="soap", name="Soap", quantity=1, unit_price="40"))
    with pytest.raises(OutOfStockError):
        reserve_stock(db, cart)
    assert get_product_by_id(db, "chiura").reserved == 0
    cart.items.pop()
    reserve_stock(db, cart)
    commit_stock(db, cart)
    p = get_product_by_id(db, "chiura")
    assert p.stock_on_hand == 8 and p.reserved == 0


def test_order_service(db, seed_products):
    c = create_conversation(db, uuid4())
    c.customer_name, c.customer_phone = "Sita", "+9779841234567"
    cart = cart_add_item(c.ensure_cart(), seed_products[0], 2)
    begin_confirmation(cart, c.customer_name, c.customer_phone)
    reserve_stock(db, cart)
    token = cart.confirmation_token
    c.messages.append(Message(role=MessageRole.user, created_at=utcnow() + timedelta(seconds=1)))
    order = place_order_from_cart(db, c, token)
    assert order.total == Decimal("250.00")
    assert place_order_from_cart(db, c, token).order_id == order.order_id
    assert get_product_by_id(db, "chiura").stock_on_hand == 8
    assert get_product_by_id(db, "chiura").reserved == 0
    assert not cart.items and cart.status == CartStatus.browsing
    assert len(list(db.scalars(select(OrderORM)))) == 1
    assert db.scalar(select(CartEventORM)).items[0]["unit_price"] == "125.00"
    with pytest.raises(TokenMismatchError):
        place_order_from_cart(db, Conversation(), token)
    with pytest.raises(InvalidStateError):
        build_order(Conversation(), cart)
    with pytest.raises(ValidationAppError):
        insert_order(db, order.model_copy(update={"confirmation_token": None}))


def test_jobs(db, seed_products, settings):
    for age in [0, settings.cart_ttl_minutes + 1]:
        c = create_conversation(db, uuid4())
        cart = cart_add_item(c.ensure_cart(), seed_products[0], 1)
        begin_confirmation(cart, "Sita", "+9779841234567")
        reserve_stock(db, cart)
        cart.updated_at -= timedelta(minutes=age)
        save_conversation(db, c)
    assert expire_stale_carts(db, settings) == 1
    assert get_product_by_id(db, "chiura").reserved == 1
    assert db.scalar(select(CartEventORM)).event_type == "cart_expired"
