from collections.abc import Sequence
from typing import Any

from anthropic import Anthropic, AnthropicError
from anthropic.types import (
    MessageParam,
    TextBlockParam,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlockParam,
)

from app.domain.enums import MessageRole
from app.domain.errors import ProviderError
from app.domain.models import Message, ToolCall, Usage
from app.llm.types import LLMResponse, ToolSpec


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float, max_retries: int = 2) -> None:
        self.model = model
        self.client = Anthropic(api_key=api_key, timeout=timeout, max_retries=max_retries)

    def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec], **opts: Any
    ) -> LLMResponse:
        system = "\n\n".join(m.content or "" for m in messages if m.role == MessageRole.system)
        wire: list[MessageParam] = []
        pending: list[ToolResultBlockParam] = []
        for message in messages:
            if message.role == MessageRole.system:
                continue
            if message.role == MessageRole.tool:
                pending.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": message.tool_call_id or "",
                        "content": message.content or "",
                    }
                )
                continue
            if pending:
                wire.append({"role": "user", "content": list(pending)})
                pending = []
            if message.role == MessageRole.assistant:
                blocks: list[TextBlockParam | ToolUseBlockParam] = []
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
                blocks.extend(
                    {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                    for c in message.tool_calls
                )
                wire.append({"role": "assistant", "content": blocks})
            else:
                wire.append({"role": "user", "content": message.content or ""})
        if pending:
            wire.append({"role": "user", "content": pending})
        wire_tools: list[ToolParam] = [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=opts.get("max_tokens", 1024),
                temperature=opts.get("temperature", 0.2),
                system=system,
                messages=wire,
                tools=wire_tools,
            )
        except AnthropicError as exc:
            raise ProviderError("Anthropic request failed") from exc
        calls: list[ToolCall] = []
        text: list[str] = []
        for block in response.content:
            if block.type == "text":
                text.append(block.text)
            elif block.type == "tool_use":
                if not isinstance(block.input, dict):
                    raise ProviderError("Anthropic returned non-object tool arguments")
                calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))
        return LLMResponse(
            content="\n".join(text) or None,
            tool_calls=calls,
            usage=Usage(
                input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens
            ),
            provider=self.name,
            model=self.model,
        )
