import json
from uuid import uuid4

import pytest

from app.core.time import utcnow
from app.domain.enums import CartStatus, MessageRole, ToolErrorCode
from app.domain.models import Message
from app.llm.types import ToolSpec
from app.repo.conversation import create_conversation
from app.repo.product import get_product_by_id
from app.tools import build_tool_registry
from app.tools.args import NoArgs
from app.tools.context import ToolContext


@pytest.fixture
def ctx(db, seed_products, fake_embedder, settings):
    return ToolContext(db, create_conversation(db, uuid4()), fake_embedder, settings, "test")


def test_tool_registry(ctx):
    registry = build_tool_registry()
    assert len(registry.specs()) == 12
    assert len({spec.name for spec in registry.specs()}) == 12
    assert '"title"' not in json.dumps([s.parameters for s in registry.specs()])
    assert registry.execute("unknown", {}, ctx).error_code == ToolErrorCode.unknown_tool
    assert registry.execute("get_product", {}, ctx).error_code == ToolErrorCode.invalid_args
    assert registry.execute("get_product", {"product_id": "missing"}, ctx).error_code == "not_found"
    with pytest.raises(ValueError):
        registry.register(registry.specs()[0], NoArgs, lambda a, c: None)

    def fail(args, context):
        raise RuntimeError("failure")

    registry.register(ToolSpec(name="fail", description="fail", parameters={}), NoArgs, fail)
    assert registry.execute("fail", {}, ctx).error_code == ToolErrorCode.internal_error


def test_tools(ctx):
    registry = build_tool_registry()

    def execute(name, args=None):
        result = registry.execute(name, args or {}, ctx)
        assert result.ok, result
        return result.data

    assert execute("search_products", {"query": "chiura"})["hits"][0]["product_id"] == "chiura"
    assert "embedding" not in json.dumps(execute("get_product", {"product_id": "chiura"}))
    execute("view_cart")
    execute("add_to_cart", {"product_id": "chiura", "quantity": 2})
    execute("update_cart_item", {"product_id": "chiura", "quantity": 3})
    execute("set_customer_info", {"name": " Sita ", "phone": "9841234567"})
    assert ctx.conversation.customer_name == "Sita"
    execute("request_order_confirmation")
    execute("request_order_confirmation")
    assert get_product_by_id(ctx.db, "chiura").reserved == 3
    execute("add_to_cart", {"product_id": "chiura", "quantity": 1})
    assert get_product_by_id(ctx.db, "chiura").reserved == 0
    assert ctx.conversation.cart.status == CartStatus.browsing
    execute("request_order_confirmation")
    execute("update_cart_item", {"product_id": "chiura", "quantity": 2})
    execute("request_order_confirmation")
    execute("remove_from_cart", {"product_id": "chiura"})
    execute("add_to_cart", {"product_id": "chiura", "quantity": 1})
    execute("request_order_confirmation")
    execute("cancel_cart")
    assert get_product_by_id(ctx.db, "chiura").reserved == 0
    execute("add_to_cart", {"product_id": "chiura", "quantity": 1})
    token = execute("request_order_confirmation")["confirmation_token"]
    ctx.conversation.messages.append(
        Message(role=MessageRole.user, content="yes", created_at=utcnow())
    )
    assert execute("place_order", {"confirmation_token": token})["total"] == "125.00"
    assert execute("search_knowledge", {"query": "hours"}) == {"hits": []}
    assert execute("handoff_to_human", {"reason": "person"})["handoff"]


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("search_products", {"query": ""}),
        ("get_product", {"product_id": "missing"}),
        ("add_to_cart", {"product_id": "missing", "quantity": 1}),
        ("update_cart_item", {"product_id": "missing", "quantity": 1}),
        ("remove_from_cart", {"product_id": "missing"}),
        ("view_cart", {"extra": 1}),
        ("set_customer_info", {"name": "Sita", "phone": "1234567"}),
        ("set_customer_info", {"name": "  ", "phone": "9841234567"}),
        ("request_order_confirmation", {}),
        ("place_order", {"confirmation_token": "wrong"}),
        ("cancel_cart", {"extra": 1}),
        ("search_knowledge", {"query": ""}),
        ("handoff_to_human", {"reason": ""}),
    ],
)
def test_tool_failures(ctx, name, args):
    assert not build_tool_registry().execute(name, args, ctx).ok
