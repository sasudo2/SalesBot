from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import OrderItemORM, OrderORM
from app.domain.errors import ValidationAppError
from app.domain.models import Order


def get_order_by_idempotency_key(db: Session, key: str) -> Order | None:
    orm = db.scalar(
        select(OrderORM)
        .where(OrderORM.idempotency_key == key)
        .options(selectinload(OrderORM.items))
    )
    if orm is None:
        return None
    return Order.model_validate(orm).model_copy(update={"confirmation_token": orm.idempotency_key})


def insert_order(db: Session, order: Order) -> Order:
    if not order.confirmation_token:
        raise ValidationAppError("An order requires a confirmation token")
    orm = OrderORM(
        order_id=order.order_id,
        conversation_id=order.conversation_id,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        status=order.status.value,
        total=order.total,
        currency=order.currency,
        idempotency_key=order.confirmation_token,
        created_at=order.created_at,
        items=[OrderItemORM(**item.model_dump()) for item in order.items],
    )
    db.add(orm)
    db.flush()
    return Order.model_validate(orm).model_copy(update={"confirmation_token": orm.idempotency_key})
