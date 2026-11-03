import logging
from collections.abc import Callable, Sequence
from typing import Any

from app.domain.errors import AllProvidersFailedError, ProviderError
from app.domain.models import Message
from app.llm.base import LLMProvider
from app.llm.types import LLMResponse, ToolSpec

logger = logging.getLogger(__name__)


class LLMProviderRegister:
    def __init__(self, default: str, fallback: list[str]) -> None:
        self.default = default
        self.fallback = list(fallback)
        self._factories: dict[str, Callable[[], LLMProvider]] = {}
        self._instance: dict[str, LLMProvider] = {}

    def register(self, name: str, factory: Callable[[], LLMProvider]) -> None:
        self._factories[name] = factory

    def _get(self, name: str) -> LLMProvider:
        if name not in self._factories:
            raise ProviderError("Unknown LLM provider")
        if name not in self._instance:
            self._instance[name] = self._factories[name]()
        return self._instance[name]

    def complete(
        self, name: str | None, messages: Sequence[Message], tools: Sequence[ToolSpec], **opts: Any
    ) -> LLMResponse:
        first = name or self.default
        for candidate in [first] + [f for f in self.fallback if f != first]:
            try:
                provider = self._get(candidate)
                response = provider.complete(messages, tools, **opts)
                response.provider = response.provider or provider.name
                response.model = response.model or str(getattr(provider, "model", provider.name))
                return response
            except ProviderError as exc:
                cause = exc.__cause__ or exc
                instance = self._instance.get(candidate)
                logger.warning(
                    "LLM provider %s failed (model=%s, error=%s, status=%s)",
                    candidate,
                    getattr(instance, "model", "unknown"),
                    type(cause).__name__,
                    getattr(cause, "status_code", None),
                )
        raise AllProvidersFailedError("All LLM providers failed")
