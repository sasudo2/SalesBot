from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from app.domain.models import Message
from app.llm.types import LLMResponse, ToolSpec


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec], **opts: Any
    ) -> LLMResponse: ...
