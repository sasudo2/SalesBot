from collections.abc import Sequence
from copy import deepcopy
from typing import Any

from app.domain.errors import ProviderError
from app.domain.models import Message
from app.llm.types import LLMResponse, ToolSpec


class FakeProvider:
    name = "fake"

    def __init__(self, script: list[LLMResponse]) -> None:
        self.script = list(script)
        self.calls: list[tuple[list[Message], list[ToolSpec], dict[str, Any]]] = []

    def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec], **opts: Any
    ) -> LLMResponse:
        self.calls.append((deepcopy(list(messages)), list(tools), dict(opts)))
        if not self.script:
            raise ProviderError("fake script exhausted")
        return self.script.pop(0)
