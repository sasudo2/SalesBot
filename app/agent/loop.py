import json
import time
from copy import deepcopy

from app.agent.prompt import build_llm_messages
from app.core.config import Settings
from app.db.models import ToolCallLogORM
from app.domain.enums import MessageRole
from app.domain.errors import AgentLoopLimitError
from app.domain.models import Conversation, Message, ToolCall
from app.llm.register import LLMProviderRegister
from app.llm.types import LLMResponse
from app.tools.context import ToolContext
from app.tools.registry import ToolRegistry
from app.tools.types import ToolResult


def generate_response(
    conversation: Conversation, llm: LLMProviderRegister, tools: ToolRegistry, settings: Settings
) -> LLMResponse:
    response = llm.complete(
        None,
        build_llm_messages(conversation, settings),
        tools.specs(),
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )
    conversation.messages.append(
        Message(
            role=MessageRole.assistant,
            content=response.content,
            tool_calls=response.tool_calls,
            usage=response.usage,
        )
    )
    return response


def tool_execution(
    call: ToolCall, ctx: ToolContext, tools: ToolRegistry
) -> tuple[ToolResult, Message, int]:
    conversation = ctx.conversation
    snapshot = (
        deepcopy(conversation.cart),
        conversation.customer_name,
        conversation.customer_phone,
        conversation.handoff,
    )
    savepoint = ctx.db.begin_nested()
    start = time.perf_counter()
    try:
        result = tools.execute(call.name, call.arguments, ctx)
        if result.ok:
            savepoint.commit()
        else:
            savepoint.rollback()
            (
                conversation.cart,
                conversation.customer_name,
                conversation.customer_phone,
                conversation.handoff,
            ) = snapshot
    except Exception:
        savepoint.rollback()
        (
            conversation.cart,
            conversation.customer_name,
            conversation.customer_phone,
            conversation.handoff,
        ) = snapshot
        raise
    latency = int((time.perf_counter() - start) * 1000)
    message = Message(
        role=MessageRole.tool,
        tool_call_id=call.id,
        content=json.dumps(result.model_dump(mode="json")),
    )
    return result, message, latency


def log_tool_call(ctx: ToolContext, call: ToolCall, result: ToolResult, latency_ms: int) -> None:
    ctx.db.add(
        ToolCallLogORM(
            conversation_id=ctx.conversation.conversation_id,
            request_id=ctx.request_id,
            tool_name=call.name,
            arguments={
                key: "***" if key == "confirmation_token" else value
                for key, value in call.arguments.items()
            },
            status="ok" if result.ok else "error",
            error_code=result.error_code.value if result.error_code else None,
            latency_ms=latency_ms,
        )
    )


def agentic_loop(
    query: str,
    conversation: Conversation,
    ctx: ToolContext,
    llm: LLMProviderRegister,
    tools: ToolRegistry,
) -> Message:
    conversation.messages.append(Message(role=MessageRole.user, content=query))
    response = generate_response(conversation, llm, tools, ctx.settings)
    iterations = 0
    while response.tool_calls:
        if iterations >= ctx.settings.max_agent_iterations:
            raise AgentLoopLimitError("Agent exceeded the tool-call limit")
        for call in response.tool_calls:
            result, message, latency = tool_execution(call, ctx, tools)
            conversation.messages.append(message)
            log_tool_call(ctx, call, result, latency)
        response = generate_response(conversation, llm, tools, ctx.settings)
        iterations += 1
    return conversation.messages[-1]
