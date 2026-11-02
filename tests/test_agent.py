import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.agent.loop import agentic_loop, log_tool_call, tool_execution
from app.agent.prompt import build_llm_messages, build_system_prompt
from app.agent.summary import summarize_if_needed
from app.db.models import ToolCallLogORM
from app.domain.enums import MessageRole
from app.domain.errors import AgentLoopLimitError
from app.domain.models import Conversation, Message, ToolCall
from app.llm.fake_provider import FakeProvider
from app.llm.register import LLMProviderRegister
from app.llm.types import LLMResponse
from app.repo.conversation import create_conversation
from app.repo.product import get_product_by_id
from app.tools import build_tool_registry
from app.tools.context import ToolContext


def _register(*responses):
    fake = FakeProvider(list(responses))
    register = LLMProviderRegister("fake", [])
    register.register("fake", lambda: fake)
    return register, fake


def test_prompt_and_windowing(settings, seed_products):
    c = Conversation(customer_name="Sita", customer_phone="+9779841234567", summary="old")
    from app.services.cart import cart_add_item

    cart_add_item(c.ensure_cart(), seed_products[0], 2)
    prompt = build_system_prompt(c, settings)
    assert all(f"{i}." in prompt for i in range(1, 11))
    assert "Sita" in prompt and "2 x Beaten rice @ 125.00" in prompt
    assert "old" in prompt and "Himal Mart" in prompt
    c.messages = [
        Message(role=MessageRole.user, content="hi"),
        Message(role=MessageRole.assistant, tool_calls=[ToolCall(id="1", name="x")]),
        Message(role=MessageRole.tool, tool_call_id="1", content="ok"),
        Message(role=MessageRole.assistant, content="done"),
        Message(role=MessageRole.user, content="next"),
    ]
    settings.history_window = 3
    assert build_llm_messages(c, settings)[1].role == MessageRole.user
    c.summarized_upto = 4
    assert build_llm_messages(c, settings)[1].content == "next"
    c.summarized_upto = len(c.messages)
    assert build_llm_messages(c, settings)[1].role == MessageRole.user


def test_summary(settings):
    settings.summary_threshold = 3
    settings.summary_batch = 2
    settings.history_window = 2
    c = Conversation(
        summary="previous",
        messages=[
            Message(role=MessageRole.user, content="first"),
            Message(role=MessageRole.assistant, content="answer"),
            Message(role=MessageRole.tool, content="SECRET TOOL DATA"),
            Message(role=MessageRole.user, content="last"),
            Message(role=MessageRole.assistant, content="end"),
        ],
    )
    llm, fake = _register(LLMResponse(content="summary"))
    summarize_if_needed(c, llm, settings)
    assert c.summary == "summary" and c.summarized_upto == 3
    assert "SECRET TOOL DATA" not in fake.calls[0][0][1].content
    assert "previous" in fake.calls[0][0][1].content
    summarize_if_needed(c, llm, settings)
    assert len(fake.calls) == 1
    c.summarized_upto = 0
    summarize_if_needed(c, llm, settings)
    assert c.summarized_upto == 0
    settings.summary_threshold = 10
    summarize_if_needed(c, llm, settings)
    assert len(fake.calls) == 2


def test_agent_loop(db, seed_products, fake_embedder, settings):
    c = create_conversation(db, uuid4())
    ctx = ToolContext(db, c, fake_embedder, settings, "request")
    llm, fake = _register(
        LLMResponse(
            tool_calls=[
                ToolCall(
                    id="1", name="add_to_cart", arguments={"product_id": "chiura", "quantity": 2}
                ),
                ToolCall(
                    id="2",
                    name="update_cart_item",
                    arguments={"product_id": "chiura", "quantity": 3},
                ),
                ToolCall(id="3", name="place_order", arguments={"confirmation_token": "private"}),
            ]
        ),
        LLMResponse(content="done"),
    )
    final = agentic_loop("hello", c, ctx, llm, build_tool_registry())
    assert final.content == "done" and c.cart.items[0].quantity == 3
    tool_messages = [m for m in fake.calls[1][0] if m.role == MessageRole.tool]
    assert [m.tool_call_id for m in tool_messages] == ["1", "2", "3"]
    assert json.loads(tool_messages[-1].content)["ok"] is False
    logs = list(db.scalars(select(ToolCallLogORM).order_by(ToolCallLogORM.id)))
    assert len(logs) == 3 and logs[-1].arguments["confirmation_token"] == "***"
    settings.max_agent_iterations = 0
    llm, _ = _register(LLMResponse(tool_calls=[ToolCall(id="x", name="view_cart")]))
    with pytest.raises(AgentLoopLimitError):
        agentic_loop("again", c, ctx, llm, build_tool_registry())


def test_tool_rollback(db, seed_products, fake_embedder, settings):
    c = create_conversation(db, uuid4())
    ctx = ToolContext(db, c, fake_embedder, settings, "request")
    tools = build_tool_registry()
    for name, args in [
        ("add_to_cart", {"product_id": "chiura", "quantity": 9}),
        ("set_customer_info", {"name": "Sita", "phone": "9841234567"}),
        ("request_order_confirmation", {}),
    ]:
        assert tool_execution(ToolCall(id=name, name=name, arguments=args), ctx, tools)[0].ok
    before = c.cart.model_copy(deep=True)
    result, _, latency = tool_execution(
        ToolCall(id="bad", name="add_to_cart", arguments={"product_id": "chiura", "quantity": 2}),
        ctx,
        tools,
    )
    assert not result.ok and c.cart == before
    assert get_product_by_id(db, "chiura").reserved == 9
    log_tool_call(ctx, ToolCall(id="bad", name="add_to_cart"), result, latency)
    assert db.scalar(select(ToolCallLogORM)).status == "error"
    with pytest.raises(RuntimeError):

        class Escaping:
            def execute(self, *args):
                c.customer_name = "changed"
                raise RuntimeError("escaped")

        tool_execution(ToolCall(id="x", name="x"), ctx, Escaping())
    assert c.customer_name == "Sita"
