from uuid import UUID

from sqlalchemy.orm import Session

from app.agent.loop import agentic_loop
from app.agent.summary import summarize_if_needed
from app.core.config import Settings
from app.domain.enums import Channel, MessageRole
from app.domain.models import Conversation, Message
from app.domain.schemas import ChatRequest, ChatResponse
from app.llm.register import LLMProviderRegister
from app.rag.base import Embedder
from app.repo.conversation import create_conversation, get_conversation, save_conversation
from app.tools.context import ToolContext
from app.tools.registry import ToolRegistry


def fetch_conversation(
    db: Session, conversation_id: UUID, channel: Channel = Channel.web
) -> Conversation:
    existing = get_conversation(db, conversation_id)
    return existing if existing is not None else create_conversation(db, conversation_id, channel)


def store_conversation(db: Session, conversation: Conversation) -> Conversation:
    return save_conversation(db, conversation)


def handle_query(
    request: ChatRequest,
    db: Session,
    llm: LLMProviderRegister,
    tools: ToolRegistry,
    embedder: Embedder,
    settings: Settings,
    request_id: str,
) -> ChatResponse:
    conversation = fetch_conversation(db, request.conversation_id, request.channel)
    if conversation.handoff:
        final = Message(role=MessageRole.assistant, content=settings.handoff_reply)
        conversation.messages.extend([Message(role=MessageRole.user, content=request.query), final])
    else:
        ctx = ToolContext(db, conversation, embedder, settings, request_id)
        final = agentic_loop(request.query, conversation, ctx, llm, tools)
        summarize_if_needed(conversation, llm, settings)
    conversation = store_conversation(db, conversation)
    db.commit()
    return ChatResponse(
        conversation_id=conversation.conversation_id,
        reply=final.content or "Sorry, I could not process that. Please try again.",
        handoff=conversation.handoff,
        cart=conversation.cart.to_summary()
        if conversation.cart and conversation.cart.items
        else None,
    )
