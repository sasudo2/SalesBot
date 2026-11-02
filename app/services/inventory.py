from sqlalchemy import case, update
from sqlalchemy.orm import Session

from app.db.models import ProductORM
from app.domain.errors import OutOfStockError
from app.domain.models import Cart


def reserve_stock(db: Session, cart: Cart) -> None:
    with db.begin_nested():
        for item in cart.items:
            result = db.scalar(
                update(ProductORM)
                .where(
                    ProductORM.id == item.product_id,
                    ProductORM.active,
                    ProductORM.stock_on_hand - ProductORM.reserved >= item.quantity,
                )
                .values(reserved=ProductORM.reserved + item.quantity)
                .returning(ProductORM.id)
            )
            if result is None:
                raise OutOfStockError(
                    f"'{item.name}' is no longer available in the requested quantity"
                )


def release_stock(db: Session, cart: Cart) -> None:
    for item in cart.items:
        db.execute(
            update(ProductORM)
            .where(ProductORM.id == item.product_id)
            .values(
                reserved=case(
                    (ProductORM.reserved >= item.quantity, ProductORM.reserved - item.quantity),
                    else_=0,
                )
            )
        )


def commit_stock(db: Session, cart: Cart) -> None:
    with db.begin_nested():
        for item in cart.items:
            result = db.scalar(
                update(ProductORM)
                .where(
                    ProductORM.id == item.product_id,
                    ProductORM.reserved >= item.quantity,
                    ProductORM.stock_on_hand >= item.quantity,
                )
                .values(
                    stock_on_hand=ProductORM.stock_on_hand - item.quantity,
                    reserved=ProductORM.reserved - item.quantity,
                )
                .returning(ProductORM.id)
            )
            if result is None:
                raise OutOfStockError(
                    f"'{item.name}' is no longer available in the requested quantity"
                )
