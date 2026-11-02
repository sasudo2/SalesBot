from app.domain.enums import CartEventType, CartStatus
from app.domain.errors import NotFoundError
from app.repo.cart_event import record_cart_event
from app.repo.product import get_product_by_id
from app.services.cart import cart_add_item, cart_remove_item, cart_update_item, reset_cart
from app.services.inventory import release_stock
from app.tools.args import AddToCartArgs, NoArgs, RemoveFromCartArgs, UpdateCartItemArgs
from app.tools.context import ToolContext
from app.tools.types import ToolResult


def _release_if_awaiting(ctx: ToolContext) -> None:
    cart = ctx.conversation.ensure_cart()
    if cart.status == CartStatus.awaiting_confirmation:
        release_stock(ctx.db, cart)


def _cart_result(ctx: ToolContext) -> ToolResult:
    return ToolResult(
        ok=True, data={"cart": ctx.conversation.ensure_cart().to_summary().model_dump(mode="json")}
    )


def tool_add_to_cart(args: AddToCartArgs, ctx: ToolContext) -> ToolResult:
    _release_if_awaiting(ctx)
    # Read availability after releasing this cart's own reservation.
    product = get_product_by_id(ctx.db, args.product_id)
    if product is None:
        raise NotFoundError("Product not found")
    cart = cart_add_item(ctx.conversation.ensure_cart(), product, args.quantity)
    record_cart_event(ctx.db, ctx.conversation.conversation_id, CartEventType.item_added, cart)
    return _cart_result(ctx)


def tool_update_cart_item(args: UpdateCartItemArgs, ctx: ToolContext) -> ToolResult:
    _release_if_awaiting(ctx)
    product = get_product_by_id(ctx.db, args.product_id)
    cart = cart_update_item(ctx.conversation.ensure_cart(), args.product_id, args.quantity, product)
    event = CartEventType.item_removed if args.quantity == 0 else CartEventType.item_updated
    record_cart_event(ctx.db, ctx.conversation.conversation_id, event, cart)
    return _cart_result(ctx)


def tool_remove_from_cart(args: RemoveFromCartArgs, ctx: ToolContext) -> ToolResult:
    _release_if_awaiting(ctx)
    cart = cart_remove_item(ctx.conversation.ensure_cart(), args.product_id)
    record_cart_event(ctx.db, ctx.conversation.conversation_id, CartEventType.item_removed, cart)
    return _cart_result(ctx)


def tool_view_cart(args: NoArgs, ctx: ToolContext) -> ToolResult:
    return _cart_result(ctx)


def tool_cancel_cart(args: NoArgs, ctx: ToolContext) -> ToolResult:
    _release_if_awaiting(ctx)
    cart = reset_cart(ctx.conversation.ensure_cart())
    record_cart_event(ctx.db, ctx.conversation.conversation_id, CartEventType.cart_cancelled, cart)
    return _cart_result(ctx)
