from decimal import Decimal

import pytest

from app.domain.enums import MessageRole
from app.domain.errors import AppError, ValidationAppError
from app.domain.models import CartItem, Conversation, Message, Product
from app.domain.validators import validate_phone


def test_domain_models():
    conversation = Conversation()
    assert conversation.last_user_message is None
    cart = conversation.ensure_cart()
    assert conversation.ensure_cart() is cart
    cart.items.append(
        CartItem(product_id="rice", name="Rice", quantity=2, unit_price=Decimal("125.00"))
    )
    assert cart.items[0].line_total == cart.total == Decimal("250.00")
    assert cart.to_summary().items == cart.items
    user = Message(role=MessageRole.user, content="hi")
    conversation.messages = [user, Message(role=MessageRole.assistant, content="hello")]
    assert conversation.last_user_message is user
    assert (
        Product(id="rice", sku="rice", name="Rice", price=10, stock_on_hand=5, reserved=2).available
        == 3
    )
    error = AppError("bad", code=ValidationAppError.code, http_status=422)
    assert error.message == "bad" and error.http_status == 422


@pytest.mark.parametrize(
    "phone", ["9841234567", "+977 98-41234567", "977(984)1234567", "9741234567"]
)
def test_validate_phone(phone):
    assert validate_phone(phone).startswith("+977")


@pytest.mark.parametrize("phone", ["984", "9641234567", "984123456a", "+19841234567"])
def test_invalid_phone(phone):
    with pytest.raises(ValidationAppError, match="Invalid Nepal"):
        validate_phone(phone)
