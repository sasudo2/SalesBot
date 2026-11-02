import json
import secrets

from app.core.hashing import sha256_hex
from app.core.time import utcnow
from app.domain.enums import CartStatus
from app.domain.errors import (
    CartChangedError,
    InvalidStateError,
    NotFoundError,
    OutOfStockError,
    TokenMismatchError,
    ValidationAppError,
)
from app.domain.models import Cart, CartItem, Conversation, Product


def _touch(cart: Cart) -> Cart:
    cart.status = CartStatus.browsing
    cart.cart_hash = None
    cart.confirmation_token = None
    cart.updated_at = utcnow()
    return cart


def cart_add_item(cart: Cart, product: Product, quantity: int) -> Cart:
    if quantity < 1:
        raise ValidationAppError("Quantity must be positive")
    line = next((i for i in cart.items if i.product_id == product.id), None)
    total = quantity + (line.quantity if line else 0)
    if total > product.available:
        raise OutOfStockError(f"Only {product.available} of '{product.name}' available")
    if line is None:
        cart.items.append(
            CartItem(
                product_id=product.id, name=product.name, quantity=total, unit_price=product.price
            )
        )
    else:
        line.quantity, line.unit_price, line.name = total, product.price, product.name
    return _touch(cart)


def cart_update_item(
    cart: Cart, product_id: str, quantity: int, product: Product | None = None
) -> Cart:
    line = next((i for i in cart.items if i.product_id == product_id), None)
    if line is None:
        raise NotFoundError("Product is not in the cart")
    if quantity < 0:
        raise ValidationAppError("Quantity cannot be negative")
    if quantity > line.quantity and (product is None or quantity > product.available):
        raise OutOfStockError("Requested quantity is not available")
    if quantity == 0:
        cart.items.remove(line)
    else:
        line.quantity = quantity
    return _touch(cart)


def cart_remove_item(cart: Cart, product_id: str) -> Cart:
    line = next((i for i in cart.items if i.product_id == product_id), None)
    if line is None:
        raise NotFoundError("Product is not in the cart")
    cart.items.remove(line)
    return _touch(cart)


def reset_cart(cart: Cart) -> Cart:
    cart.items = []
    return _touch(cart)


def compute_cart_hash(cart: Cart, customer_name: str, customer_phone: str) -> str:
    return sha256_hex(
        json.dumps(
            {
                "n": customer_name,
                "p": customer_phone,
                "i": sorted([[i.product_id, i.quantity, str(i.unit_price)] for i in cart.items]),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def begin_confirmation(cart: Cart, customer_name: str | None, customer_phone: str | None) -> Cart:
    if not cart.items:
        raise InvalidStateError("Cart is empty")
    if not customer_name or not customer_phone:
        raise InvalidStateError(
            "Customer name and phone are required. Call set_customer_info first."
        )
    cart.cart_hash = compute_cart_hash(cart, customer_name, customer_phone)
    cart.confirmation_token = secrets.token_urlsafe(32)
    cart.status = CartStatus.awaiting_confirmation
    cart.updated_at = utcnow()
    return cart


def assert_confirmable(conversation: Conversation, token: str) -> None:
    cart = conversation.cart
    if cart is None or not cart.items:
        raise InvalidStateError("Cart is empty")
    if cart.status != CartStatus.awaiting_confirmation:
        raise InvalidStateError("Cart is not awaiting confirmation")
    if not secrets.compare_digest(token, cart.confirmation_token or ""):
        raise TokenMismatchError("Confirmation token does not match")
    if (
        compute_cart_hash(cart, conversation.customer_name or "", conversation.customer_phone or "")
        != cart.cart_hash
    ):
        raise CartChangedError("Cart or customer details have changed. Request confirmation again.")
    last = conversation.last_user_message
    if last is None or cart.updated_at >= last.created_at:
        raise InvalidStateError(
            "The customer must confirm in a new message before the order can be placed."
        )
