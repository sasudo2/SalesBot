from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.core.time import utcnow
from app.db.models import CartItemORM, CartORM, ConversationORM, MessageORM
from app.domain.enums import Channel
from app.domain.errors import ConflictError, NotFoundError
from app.domain.models import Conversation


def get_conversation(db: Session, conversation_id: UUID) -> Conversation | None:
    orm = db.scalar(
        select(ConversationORM)
        .where(ConversationORM.conversation_id == conversation_id)
        .options(
            selectinload(ConversationORM.messages),
            selectinload(ConversationORM.cart).selectinload(CartORM.items),
        )
    )
    if orm is None:
        return None
    _retain(db, orm)
    return Conversation.model_validate(orm)


def create_conversation(
    db: Session, conversation_id: UUID, channel: Channel = Channel.web
) -> Conversation:
    orm = ConversationORM(conversation_id=conversation_id, channel=channel.value)
    db.add(orm)
    db.flush()
    _retain(db, orm)
    return Conversation.model_validate(orm)


def _retain(db: Session, orm: ConversationORM) -> None:
    # Keep loaded cart versions alive until the request transaction ends.
    db.info.setdefault("_conversation_refs", {})[orm.conversation_id] = orm


def apply_conversation_to_orm(conversation: Conversation, orm: ConversationORM) -> ConversationORM:
    orm.channel = conversation.channel.value
    orm.customer_name = conversation.customer_name
    orm.customer_phone = conversation.customer_phone
    orm.handoff = conversation.handoff
    orm.summary = conversation.summary
    orm.summarized_upto = conversation.summarized_upto
    orm.last_updated = utcnow()
    stored = len(orm.messages)
    for i, message in enumerate(conversation.messages):
        if i >= stored:
            orm.messages.append(
                MessageORM(
                    seq=i,
                    role=message.role.value,
                    content=message.content,
                    tool_calls=[t.model_dump() for t in message.tool_calls],
                    tool_call_id=message.tool_call_id,
                    usage=message.usage.model_dump() if message.usage else None,
                    created_at=message.created_at,
                )
            )
    cart = conversation.cart
    if cart is None:
        orm.cart = None
    else:
        if orm.cart is None:
            orm.cart = CartORM(conversation_id=conversation.conversation_id)
        orm.cart.status = cart.status.value
        orm.cart.cart_hash = cart.cart_hash
        orm.cart.confirmation_token = cart.confirmation_token
        orm.cart.updated_at = cart.updated_at
        existing = {item.product_id: item for item in orm.cart.items}
        synced: list[CartItemORM] = []
        for item in cart.items:
            line = existing.get(item.product_id)
            if line is None:
                line = CartItemORM(product_id=item.product_id)
            line.name, line.quantity, line.unit_price = item.name, item.quantity, item.unit_price
            synced.append(line)
        orm.cart.items = synced
    return orm


def save_conversation(db: Session, conversation: Conversation) -> Conversation:
    orm = db.get(ConversationORM, conversation.conversation_id)
    if orm is None:
        raise NotFoundError("Conversation not found")
    if orm.version != conversation.version:
        raise ConflictError("Conversation was modified by another request. Please retry.")
    apply_conversation_to_orm(conversation, orm)
    try:
        db.flush()
    except StaleDataError as exc:
        raise ConflictError("Conversation was modified by another request. Please retry.") from exc
    db.refresh(orm)
    return Conversation.model_validate(orm)
