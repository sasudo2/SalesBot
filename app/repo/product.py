from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ProductORM
from app.domain.models import Product


def get_product_by_id(db: Session, product_id: str) -> Product | None:
    orm = db.scalar(select(ProductORM).where(ProductORM.id == product_id, ProductORM.active))
    return Product.model_validate(orm) if orm is not None else None


def list_active_products(db: Session) -> list[Product]:
    return [
        Product.model_validate(orm)
        for orm in db.scalars(select(ProductORM).where(ProductORM.active))
    ]


def upsert_product(db: Session, product: Product) -> Product:
    orm = db.get(ProductORM, product.id)
    if orm is None:
        orm = ProductORM(id=product.id)
        db.add(orm)
    for name, value in product.model_dump().items():
        setattr(orm, name, value)
    db.flush()
    return Product.model_validate(orm)
