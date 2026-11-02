import logging

from app.tools.args import HandoffArgs
from app.tools.context import ToolContext
from app.tools.types import ToolResult

logger = logging.getLogger(__name__)


def tool_handoff_to_human(args: HandoffArgs, ctx: ToolContext) -> ToolResult:
    ctx.conversation.handoff = True
    logger.info("Conversation handed off to a human")
    return ToolResult(ok=True, data={"handoff": True})
