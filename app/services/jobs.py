from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, load_settings
from app.core.time import utcnow
from app.db.models import CartORM
from app.db.session import get_sessionmaker
from app.domain.enums import CartEventType, CartStatus
from app.domain.models import Cart
from app.repo.cart_event import record_cart_event
from app.services.inventory import release_stock


def expire_stale_carts(db: Session, settings: Settings) -> int:
    carts = list(
        db.scalars(
            select(CartORM)
            .where(
                CartORM.status == CartStatus.awaiting_confirmation.value,
                CartORM.updated_at < utcnow() - timedelta(minutes=settings.cart_ttl_minutes),
            )
            .options(selectinload(CartORM.items))
            .with_for_update(skip_locked=True)
        )
    )
    for orm in carts:
        cart = Cart.model_validate(orm)
        release_stock(db, cart)
        record_cart_event(db, cart.conversation_id, CartEventType.cart_expired, cart)
        orm.status = CartStatus.browsing.value
        orm.cart_hash = None
        orm.confirmation_token = None
        orm.updated_at = utcnow()
    return len(carts)


def run_expiry_once() -> int:
    with get_sessionmaker()() as db:
        count = expire_stale_carts(db, load_settings())
        db.commit()
        return count
