from app.domain.errors import ValidationAppError
from app.domain.validators import validate_phone
from app.tools.args import SetCustomerInfoArgs
from app.tools.context import ToolContext
from app.tools.types import ToolResult


def tool_set_customer_info(args: SetCustomerInfoArgs, ctx: ToolContext) -> ToolResult:
    phone = validate_phone(args.phone)
    name = args.name.strip()
    if len(name) < 2:
        raise ValidationAppError("Customer name must contain at least two characters")
    ctx.conversation.customer_name, ctx.conversation.customer_phone = name, phone
    return ToolResult(ok=True, data={"customer_name": name, "customer_phone": phone})
