from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import CartEventORM
from app.domain.enums import CartEventType
from app.domain.models import Cart


def record_cart_event(
    db: Session, conversation_id: UUID, event_type: CartEventType, cart: Cart
) -> None:
    db.add(
        CartEventORM(
            conversation_id=conversation_id,
            event_type=event_type.value,
            items=[item.model_dump(mode="json") for item in cart.items],
            total=cart.total,
        )
    )
