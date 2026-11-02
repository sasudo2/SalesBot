import json
import logging
from collections.abc import Sequence
from typing import Any

from openai import OpenAI, OpenAIError
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
from openai.types.chat.completion_create_params import CompletionCreateParamsNonStreaming

from app.domain.enums import MessageRole
from app.domain.errors import ProviderError
from app.domain.models import Message, ToolCall, Usage
from app.llm.types import LLMResponse, ToolSpec

logger = logging.getLogger(__name__)


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float,
        max_retries: int = 2,
        *,
        base_url: str | None = None,
    ) -> None:
        self.model = model
        self.client = OpenAI(
            api_key=api_key, timeout=timeout, max_retries=max_retries, base_url=base_url
        )

    def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec], **opts: Any
    ) -> LLMResponse:
        wire: list[ChatCompletionMessageParam] = []
        for message in messages:
            if message.role == MessageRole.tool:
                wire.append(
                    {
                        "role": "tool",
                        "tool_call_id": message.tool_call_id or "",
                        "content": message.content or "",
                    }
                )
            elif message.role == MessageRole.assistant:
                assistant: ChatCompletionAssistantMessageParam = {
                    "role": "assistant",
                    "content": message.content,
                }
                if message.tool_calls:
                    assistant["tool_calls"] = [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                        }
                        for c in message.tool_calls
                    ]
                wire.append(assistant)
            elif message.role == MessageRole.system:
                wire.append({"role": "system", "content": message.content or ""})
            else:
                wire.append({"role": "user", "content": message.content or ""})
        wire_tools: list[ChatCompletionToolParam] = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]
        params: CompletionCreateParamsNonStreaming = {
            "model": self.model,
            "messages": wire,
            "temperature": opts.get("temperature", 0.2),
            "max_tokens": opts.get("max_tokens", 1024),
        }
        if wire_tools:
            params["tools"] = wire_tools
        try:
            response = self.client.chat.completions.create(**params)
        except OpenAIError as exc:
            raise ProviderError(f"{self.name} request failed") from exc
        if not response.choices:
            raise ProviderError(f"{self.name} returned no completion choices")
        result = response.choices[0].message
        calls: list[ToolCall] = []
        for call in result.tool_calls or []:
            if call.type != "function":
                continue
            try:
                arguments = json.loads(call.function.arguments)
            except json.JSONDecodeError:
                logger.warning("%s returned malformed tool arguments", self.name)
                arguments = {}
            if not isinstance(arguments, dict):
                logger.warning("%s returned non-object tool arguments", self.name)
                arguments = {}
            calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))
        return LLMResponse(
            content=result.content,
            tool_calls=calls,
            usage=Usage(
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
            ),
            provider=self.name,
            model=self.model,
        )
