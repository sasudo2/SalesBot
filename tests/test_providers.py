from types import SimpleNamespace
from unittest.mock import patch

import pytest
from anthropic import AnthropicError
from openai import OpenAIError

from app.domain.enums import MessageRole
from app.domain.errors import AllProvidersFailedError, ProviderError
from app.domain.models import Message, ToolCall
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.fake_provider import FakeProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.register import LLMProviderRegister
from app.llm.types import LLMResponse, ToolSpec
from app.rag.openai_embedder import OpenAIEmbedder


def _messages():
    return [
        Message(role=MessageRole.system, content="rules"),
        Message(role=MessageRole.system, content="more"),
        Message(role=MessageRole.user, content="hello"),
        Message(
            role=MessageRole.assistant,
            content="checking",
            tool_calls=[ToolCall(id="1", name="test", arguments={"a": 1})],
        ),
        Message(role=MessageRole.tool, tool_call_id="1", content="one"),
        Message(role=MessageRole.tool, tool_call_id="2", content="two"),
    ]


def test_openai():
    with patch("app.llm.openai_provider.OpenAI") as factory:
        client = factory.return_value
        create = client.chat.completions.create
        create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="ok",
                        tool_calls=[
                            SimpleNamespace(
                                type="function",
                                id="2",
                                function=SimpleNamespace(name="test", arguments='{"x": 1}'),
                            )
                        ],
                    )
                )
            ],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2),
        )
        p = OpenAIProvider("test", "model", 1)
        result = p.complete(_messages(), [ToolSpec(name="test", description="Test", parameters={})])
        assert result.usage.input_tokens == 5 and result.tool_calls[0].arguments == {"x": 1}
        request = create.call_args.kwargs
        assert request["messages"][-1]["tool_call_id"] == "2"
        assert request["messages"][3]["tool_calls"][0]["function"]["arguments"] == '{"a": 1}'
        assert request["tools"][0]["type"] == "function"
        create.return_value.choices[0].message.tool_calls[0].function.arguments = "bad"
        assert p.complete([], []).tool_calls[0].arguments == {}
        assert "tools" not in create.call_args.kwargs
        create.return_value.choices[0].message.tool_calls[0].function.arguments = "[]"
        assert p.complete([], []).tool_calls[0].arguments == {}
        create.side_effect = OpenAIError("failed")
        with pytest.raises(ProviderError):
            p.complete([], [])


def test_anthropic():
    with patch("app.llm.anthropic_provider.Anthropic") as factory:
        create = factory.return_value.messages.create
        create.return_value = SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="ok"),
                SimpleNamespace(type="tool_use", id="3", name="test", input={"a": 1}),
            ],
            usage=SimpleNamespace(input_tokens=4, output_tokens=2),
        )
        p = AnthropicProvider("test", "model", 1)
        result = p.complete([*_messages(), Message(role=MessageRole.user, content="next")], [])
        assert result.tool_calls[0].arguments == {"a": 1}
        request = create.call_args.kwargs
        assert request["system"] == "rules\n\nmore"
        assert len(request["messages"][2]["content"]) == 2
        p.complete(_messages(), [ToolSpec(name="test", description="Test", parameters={})])
        assert create.call_args.kwargs["tools"][0]["input_schema"] == {}
        create.side_effect = AnthropicError("failed")
        with pytest.raises(ProviderError):
            p.complete([], [])


def test_register():
    fake = FakeProvider([LLMResponse(content="fallback")])
    register = LLMProviderRegister("unknown", ["fake"])
    register.register("fake", lambda: fake)
    result = register.complete(None, [], [])
    assert result.content == "fallback" and result.provider == result.model == "fake"
    with pytest.raises(AllProvidersFailedError):
        register.complete("fake", [], [])
    assert len(fake.calls) == 2
    default = FakeProvider([LLMResponse(content="default")])
    register.register("unknown", lambda: default)
    assert register.complete(None, [], []).content == "default"
    assert len(fake.calls) == 2


def test_openai_embedder():
    with patch("app.rag.openai_embedder.OpenAI") as factory:
        create = factory.return_value.embeddings.create
        create.side_effect = lambda **kw: SimpleNamespace(
            data=[SimpleNamespace(index=i, embedding=[1.0]) for i, _ in enumerate(kw["input"])]
        )
        embedder = OpenAIEmbedder("test", "model")
        assert len(embedder.embed(["a"] * 101)) == 101
        assert create.call_count == 2
        create.side_effect = OpenAIError("failed")
        with pytest.raises(ProviderError):
            embedder.embed(["a"])
        create.side_effect = None
        create.return_value = SimpleNamespace(data=[])
        with pytest.raises(ProviderError, match="incorrect"):
            embedder.embed(["a"])
