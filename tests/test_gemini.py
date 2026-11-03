import json
from unittest.mock import patch

import httpx
import pytest
from openai import OpenAI

from app.api.deps import _llm_register, get_llm_register
from app.core.config import Settings
from app.domain.enums import MessageRole
from app.domain.errors import AllProvidersFailedError, ProviderError
from app.domain.models import Message
from app.llm.fake_provider import FakeProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.register import LLMProviderRegister
from app.llm.types import LLMResponse, ToolSpec


def _completion():
    return {
        "id": "test",
        "object": "chat.completion",
        "created": 1,
        "model": "gemini-2.5-flash",
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


def test_gemini_tool_round_trip():
    requests = []

    def handle(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json=_completion())
        body = _completion()
        body["choices"][0]["message"] = {"role": "assistant", "content": "Your cart is empty."}
        body["choices"][0]["finish_reason"] = "stop"
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        with patch("app.llm.openai_provider.OpenAI", wraps=OpenAI) as constructor:
            provider = GeminiProvider("test-google-token", timeout=1, max_retries=0)
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        assert constructor.call_args.kwargs["base_url"] == base_url
        provider.client.close()
        provider.client = OpenAI(
            api_key="test-google-token",
            base_url=base_url,
            http_client=transport,
            max_retries=0,
        )
        result = provider.complete(
            [Message(role=MessageRole.user, content="Show my cart")],
            [ToolSpec(name="view_cart", description="View cart", parameters={"type": "object"})],
        )
        assert result.provider == "gemini" and result.model == "gemini-2.5-flash"
        assert result.usage.input_tokens == 10 and result.usage.output_tokens == 5
        assert result.tool_calls[0].name == "view_cart"
        assert str(requests[0].url) == base_url + "chat/completions"
        assert requests[0].headers["Authorization"] == "Bearer test-google-token"
        body = json.loads(requests[0].content)
        assert body["model"] == "gemini-2.5-flash"
        assert body["tools"][0]["function"]["name"] == "view_cart"
        messages = [
            Message(role=MessageRole.assistant, tool_calls=result.tool_calls),
            Message(role=MessageRole.tool, tool_call_id="call-1", content='{"ok":true}'),
        ]
        assert provider.complete(messages, []).content == "Your cart is empty."
        second = json.loads(requests[-1].content)
        assert second["messages"][-1]["tool_call_id"] == "call-1"
        assert "tools" not in second


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 503])
def test_gemini_errors_and_fallback(status, caplog):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json={"error": {"message": "unavailable"}})
        )
    ) as transport:
        provider = GeminiProvider("test", max_retries=0)
        provider.client.close()
        provider.client = OpenAI(
            api_key="test",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            http_client=transport,
            max_retries=0,
        )
        with pytest.raises(ProviderError, match="gemini request failed") as failure:
            provider.complete([], [])
        register = LLMProviderRegister("gemini", ["fake"])
        register.register("gemini", lambda: provider)
        register.register("fake", lambda: FakeProvider([LLMResponse(content="fallback")]))
        assert register.complete(None, [], []).content == "fallback"
        assert "LLM provider gemini failed" in caplog.text
        assert "model=gemini-2.5-flash" in caplog.text
        assert f"error={type(failure.value.__cause__).__name__}" in caplog.text
        assert f"status={status}" in caplog.text
        assert "unavailable" not in caplog.text
        assert "trying fallback" not in caplog.text


def test_gemini_connection_failure_logging(caplog):
    def handle(request):
        raise httpx.ConnectError("sensitive upstream details", request=request)

    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        provider = GeminiProvider("test", max_retries=0)
        provider.client.close()
        provider.client = OpenAI(api_key="test", http_client=transport, max_retries=0)
        register = LLMProviderRegister("gemini", [])
        register.register("gemini", lambda: provider)
        with pytest.raises(AllProvidersFailedError, match="All LLM providers failed"):
            register.complete(None, [], [])
        assert "error=APIConnectionError, status=None" in caplog.text
        assert "sensitive upstream details" not in caplog.text


def test_gemini_default_model(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert Settings(_env_file=None).gemini_model == "gemini-3.8-flash"


def test_gemini_environment_registration(monkeypatch):
    monkeypatch.setenv("GOOGLE_TOKEN", "test-google-token")
    monkeypatch.setenv("DEFAULT_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_MODEL", "custom-gemini-model")
    settings = Settings(_env_file=None)
    assert settings.google_token == "test-google-token"
    with patch("app.api.deps.GeminiProvider") as factory:
        register = get_llm_register(settings)
        assert register is get_llm_register(settings)
        assert register._get("gemini") is factory.return_value
        factory.assert_called_once_with(
            "test-google-token", "custom-gemini-model", settings.provider_timeout_s
        )
    _llm_register.cache_clear()


def test_gemini_missing_token():
    settings = Settings(_env_file=None, default_provider="gemini", google_token=None)
    with pytest.raises(RuntimeError, match="default"):
        get_llm_register(settings)
