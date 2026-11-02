import json
from uuid import uuid4

from sqlalchemy import select

from app.db.models import CartEventORM, OrderORM, ToolCallLogORM
from app.domain.enums import CartStatus, MessageRole
from app.domain.models import ToolCall
from app.llm.types import LLMResponse
from app.repo.conversation import get_conversation
from app.repo.product import get_product_by_id


def _call(tool_name, **arguments):
    return ToolCall(id=tool_name, name=tool_name, arguments=arguments)


def _post(client, id_, text):
    response = client.post("/chat", json={"conversation_id": str(id_), "query": text})
    assert response.status_code == 200, response.text
    return response.json()


def test_e2e_order_flow(client, db, seed_products, fake_llm):
    id_ = uuid4()
    fake_llm.script.extend(
        [
            LLMResponse(
                tool_calls=[
                    _call("search_products", query="chiura"),
                    _call("add_to_cart", product_id="chiura", quantity=2),
                ]
            ),
            LLMResponse(content="Added 2 chiura. May I have your name and phone?"),
            LLMResponse(
                tool_calls=[
                    _call("set_customer_info", name="Sita", phone="9841234567"),
                    _call("request_order_confirmation"),
                ]
            ),
            LLMResponse(content="2 chiura, NPR 250.00. Shall I place this order? (yes/no)"),
        ]
    )
    assert _post(client, id_, "I want 2 chiura")["cart"]["total"] == "250.00"
    assert "Shall I" in _post(client, id_, "my name is Sita, 9841234567")["reply"]
    c = get_conversation(db, id_)
    token = c.cart.confirmation_token
    assert get_product_by_id(db, "chiura").reserved == 2
    fake_llm.script.extend(
        [
            LLMResponse(tool_calls=[_call("place_order", confirmation_token=token)]),
            LLMResponse(content="Your order has been placed."),
        ]
    )
    assert _post(client, id_, "yes")["cart"] is None
    order = db.scalar(select(OrderORM))
    assert order.customer_phone == "+9779841234567"
    assert str(order.total) == "250.00"
    assert order.items[0].quantity == 2 and len(order.items) == 1
    assert len(list(db.scalars(select(OrderORM)))) == 1
    p = get_product_by_id(db, "chiura")
    assert p.stock_on_hand == 8 and p.reserved == 0
    c = get_conversation(db, id_)
    assert c.cart.status == CartStatus.browsing and c.cart.items == []
    events = list(db.scalars(select(CartEventORM).order_by(CartEventORM.id)))
    assert [e.event_type for e in events] == ["item_added", "confirmation_request", "order_placed"]
    logs = list(db.scalars(select(ToolCallLogORM).order_by(ToolCallLogORM.id)))
    assert len(logs) == 5
    assert logs[-1].arguments["confirmation_token"] == "***"


def test_same_turn_order_rejected(client, db, seed_products, fake_llm, monkeypatch):
    fake_llm.script.extend(
        [
            LLMResponse(
                tool_calls=[
                    _call("add_to_cart", product_id="chiura", quantity=2),
                    _call("set_customer_info", name="Sita", phone="9841234567"),
                    _call("request_order_confirmation"),
                ]
            ),
            LLMResponse(content="SAME_TURN"),
            LLMResponse(content="Please confirm in your next message."),
        ]
    )
    complete = fake_llm.complete

    def with_token(messages, tools, **opts):
        response = complete(messages, tools, **opts)
        if response.content == "SAME_TURN":
            result = json.loads(messages[-1].content)
            return LLMResponse(
                tool_calls=[
                    _call("place_order", confirmation_token=result["data"]["confirmation_token"])
                ]
            )
        return response

    monkeypatch.setattr(fake_llm, "complete", with_token)
    id_ = uuid4()
    _post(client, id_, "2 chiura, Sita, 9841234567")
    assert not list(db.scalars(select(OrderORM)))
    assert get_product_by_id(db, "chiura").reserved == 2
    c = get_conversation(db, id_)
    tool_messages = [m for m in c.messages if m.role == MessageRole.tool]
    assert json.loads(tool_messages[-1].content)["error_code"] == "invalid_state"
