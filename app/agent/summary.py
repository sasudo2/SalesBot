import logging

from app.core.config import Settings
from app.domain.enums import MessageRole
from app.domain.errors import AppError
from app.domain.models import Conversation, Message
from app.llm.register import LLMProviderRegister

logger = logging.getLogger(__name__)


def summarize_if_needed(
    conversation: Conversation, llm: LLMProviderRegister, settings: Settings
) -> None:
    messages = conversation.messages
    if len(messages) <= settings.summary_threshold:
        return
    boundary = max(0, len(messages) - settings.history_window)
    boundary = min(boundary, len(messages))
    while boundary > 0 and (
        boundary == len(messages) or messages[boundary].role != MessageRole.user
    ):
        boundary -= 1
    if boundary - conversation.summarized_upto < settings.summary_batch:
        return
    transcript = "\n".join(
        f"{m.role.value}: {m.content or ''}"
        for m in messages[conversation.summarized_upto : boundary]
        if m.role in (MessageRole.user, MessageRole.assistant) and m.content
    )
    try:
        response = llm.complete(
            None,
            [
                Message(
                    role=MessageRole.system,
                    content="Summarise this sales conversation for the assistant's memory "
                    "in at most 150 words: customer preferences, products discussed, "
                    "cart status, open questions.",
                ),
                Message(
                    role=MessageRole.user,
                    content=(conversation.summary or "") + "\n" + transcript,
                ),
            ],
            [],
        )
    except AppError:
        logger.warning("Conversation summarisation failed")
        return
    conversation.summary = response.content
    conversation.summarized_upto = boundary
