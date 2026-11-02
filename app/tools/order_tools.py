from app.domain.enums import CartEventType, CartStatus
from app.repo.cart_event import record_cart_event
from app.services.cart import begin_confirmation
from app.services.inventory import release_stock, reserve_stock
from app.services.order import place_order_from_cart
from app.tools.args import NoArgs, PlaceOrderArgs
from app.tools.context import ToolContext
from app.tools.types import ToolResult


def tool_request_confirmation(args: NoArgs, ctx: ToolContext) -> ToolResult:
    conversation = ctx.conversation
    cart = conversation.ensure_cart()
    if cart.status == CartStatus.awaiting_confirmation:
        release_stock(ctx.db, cart)
    begin_confirmation(cart, conversation.customer_name, conversation.customer_phone)
    reserve_stock(ctx.db, cart)
    record_cart_event(
        ctx.db, conversation.conversation_id, CartEventType.confirmation_request, cart
    )
    return ToolResult(
        ok=True,
        data={
            "cart": cart.to_summary().model_dump(mode="json"),
            "confirmation_token": cart.confirmation_token,
            "customer_name": conversation.customer_name,
            "customer_phone": conversation.customer_phone,
        },
    )


def tool_place_order(args: PlaceOrderArgs, ctx: ToolContext) -> ToolResult:
    order = place_order_from_cart(
        ctx.db, ctx.conversation, args.confirmation_token, ctx.settings.currency
    )
    return ToolResult(
        ok=True,
        data=order.model_dump(
            mode="json", include={"order_id", "total", "currency", "status", "items"}
        ),
    )
