import json
from unittest.mock import patch

import httpx
import pytest
from openai import OpenAI

from app.api.deps import _llm_register, get_llm_register
from app.core.config import Settings
from app.domain.enums import MessageRole
from app.domain.errors import AllProvidersFailedError
from app.domain.models import Message
from app.llm.fake_provider import FakeProvider
from app.llm.nvidia_provider import NvidiaProvider
from app.llm.register import LLMProviderRegister
from app.llm.types import LLMResponse, ToolSpec


def test_nvidia_request_and_tool_round_trip():
    requests = []

    def handle(request):
        requests.append(request)
        message = (
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "view_cart", "arguments": "{}"},
                    }
                ],
            }
            if len(requests) == 1
            else {"role": "assistant", "content": "Your cart is empty."}
        )
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 1,
                "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls" if len(requests) == 1 else "stop",
                        "message": message,
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        provider = NvidiaProvider("test-key", timeout=1, max_retries=0)
        assert str(provider.client.base_url) == "https://integrate.api.nvidia.com/v1/"
        provider.client.close()
        provider.client = OpenAI(
            api_key="test-key",
            base_url="https://integrate.api.nvidia.com/v1",
            http_client=transport,
            max_retries=0,
        )
        result = provider.complete(
            [Message(role=MessageRole.user, content="Show my cart")],
            [ToolSpec(name="view_cart", description="View cart", parameters={"type": "object"})],
        )
        assert result.provider == "nvidia"
        assert result.model == "nvidia/nemotron-3.5-super-vl-120b-a12b"
        assert result.usage.input_tokens == 10 and result.usage.output_tokens == 5
        assert result.tool_calls[0].name == "view_cart"
        assert str(requests[0].url) == "https://integrate.api.nvidia.com/v1/chat/completions"
        assert requests[0].headers["Authorization"] == "Bearer test-key"
        body = json.loads(requests[0].content)
        assert body["model"] == "nvidia/nemotron-3.5-super-vl-120b-a12b"
        assert body["tools"][0]["function"]["name"] == "view_cart"
        result = provider.complete(
            [
                Message(role=MessageRole.assistant, tool_calls=result.tool_calls),
                Message(role=MessageRole.tool, tool_call_id="call-1", content='{"ok":true}'),
            ],
            [],
        )
        assert result.content == "Your cart is empty."
        body = json.loads(requests[-1].content)
        assert body["messages"][-1]["tool_call_id"] == "call-1"
        assert "tools" not in body


@pytest.mark.parametrize("status", [401, 410, 429, 503])
def test_nvidia_errors_allow_fallback(status):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json={"error": {"message": "unavailable"}})
        )
    ) as transport:
        provider = NvidiaProvider("test", max_retries=0)
        provider.client.close()
        provider.client = OpenAI(
            api_key="test",
            base_url="https://integrate.api.nvidia.com/v1",
            http_client=transport,
            max_retries=0,
        )
        register = LLMProviderRegister("nvidia", ["fake"])
        register.register("nvidia", lambda: provider)
        register.register("fake", lambda: FakeProvider([LLMResponse(content="fallback")]))
        assert register.complete(None, [], []).content == "fallback"
        register.fallback = []
        with pytest.raises(AllProvidersFailedError):
            register.complete(None, [], [])


def test_nvidia_environment_registration(monkeypatch):
    monkeypatch.setenv("NVIDIA_KEY", "test-nvidia-key")
    monkeypatch.setenv("DEFAULT_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_MODEL", "custom-nvidia-model")
    settings = Settings(_env_file=None)
    assert settings.nvidia_key == "test-nvidia-key"
    try:
        with patch("app.api.deps.NvidiaProvider") as factory:
            register = get_llm_register(settings)
            assert register is get_llm_register(settings)
            assert register._get("nvidia") is factory.return_value
            factory.assert_called_once_with(
                "test-nvidia-key", "custom-nvidia-model", settings.provider_timeout_s
            )
    finally:
        _llm_register.cache_clear()


def test_nvidia_defaults(monkeypatch):
    monkeypatch.delenv("DEFAULT_PROVIDER", raising=False)
    monkeypatch.delenv("NVIDIA_MODEL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.default_provider == "nvidia"
    assert settings.nvidia_model == "nvidia/nemotron-3.5-super-vl-120b-a12b"


def test_nvidia_missing_key():
    settings = Settings(_env_file=None, default_provider="nvidia", nvidia_key=None)
    with pytest.raises(RuntimeError, match="default"):
        get_llm_register(settings)
