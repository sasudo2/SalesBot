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
from app.llm.openrouter_provider import OpenRouterProvider
from app.llm.register import LLMProviderRegister
from app.llm.types import LLMResponse, ToolSpec


def _completion():
    return {
        "id": "test",
        "object": "chat.completion",
        "created": 1,
        "model": "example/free-model:free",
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "view_cart", "arguments": "{}"},
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def test_openrouter_request_and_tool_round_trip():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=_completion())

    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        with patch("app.llm.openai_provider.OpenAI", wraps=OpenAI) as constructor:
            provider = OpenRouterProvider("test-token", timeout=1, max_retries=0)
            provider.client.close()
            provider.client = OpenAI(
                api_key="test-token",
                base_url="https://openrouter.ai/api/v1",
                http_client=transport,
                max_retries=0,
            )
        assert constructor.call_args.kwargs["base_url"] == "https://openrouter.ai/api/v1"
        result = provider.complete(
            [Message(role=MessageRole.user, content="Show my cart")],
            [ToolSpec(name="view_cart", description="View cart", parameters={"type": "object"})],
        )
        assert result.provider == "openrouter"
        assert result.tool_calls[0].name == "view_cart"
        assert result.usage.input_tokens == 10
        assert str(requests[0].url) == "https://openrouter.ai/api/v1/chat/completions"
        assert requests[0].headers["Authorization"] == "Bearer test-token"
        body = json.loads(requests[0].content)
        assert body["model"] == "openrouter/free"
        assert body["tools"][0]["function"]["name"] == "view_cart"
        provider.complete(
            [
                Message(role=MessageRole.assistant, tool_calls=result.tool_calls),
                Message(role=MessageRole.tool, tool_call_id="call-1", content='{"ok":true}'),
            ],
            [],
        )
        assert "tools" not in json.loads(requests[-1].content)


@pytest.mark.parametrize("status", [401, 429, 503, 200])
def test_openrouter_errors_allow_fallback(status):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status, json={"error": {"message": "unavailable"}, "choices": []}
            )
        )
    ) as transport:
        provider = OpenRouterProvider("test", max_retries=0)
        provider.client.close()
        provider.client = OpenAI(
            api_key="test",
            base_url="https://openrouter.ai/api/v1",
            http_client=transport,
            max_retries=0,
        )
        register = LLMProviderRegister("openrouter", [])
        register.register("openrouter", lambda: provider)
        with pytest.raises(AllProvidersFailedError):
            register.complete(None, [], [])


def test_environment_registration(monkeypatch):
    monkeypatch.setenv("OPENROUTER_TOKEN", "test-token")
    monkeypatch.setenv("DEFAULT_PROVIDER", "openrouter")
    settings = Settings(_env_file=None)
    assert settings.openrouter_token == "test-token"
    assert settings.openrouter_model == "openrouter/free"
    with patch("app.api.deps.OpenRouterProvider") as factory:
        register = get_llm_register(settings)
        assert register._get("openrouter") is factory.return_value
        factory.assert_called_once_with(
            "test-token", "openrouter/free", settings.provider_timeout_s
        )
    _llm_register.cache_clear()


def test_missing_token_is_configuration_error():
    settings = Settings(
        _env_file=None,
        default_provider="openrouter",
        openrouter_token=None,
    )
    with pytest.raises(RuntimeError, match="default"):
        get_llm_register(settings)


def test_openrouter_failure_uses_explicit_fallback():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, json={"error": {"message": "rate limited"}})
        )
    ) as transport:
        provider = OpenRouterProvider("test", max_retries=0)
        provider.client.close()
        provider.client = OpenAI(
            api_key="test",
            base_url="https://openrouter.ai/api/v1",
            http_client=transport,
            max_retries=0,
        )
        fake = FakeProvider([LLMResponse(content="fallback")])
        register = LLMProviderRegister("openrouter", ["fake"])
        register.register("openrouter", lambda: provider)
        register.register("fake", lambda: fake)
        assert register.complete(None, [], []).content == "fallback"
