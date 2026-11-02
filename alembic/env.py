from typing import Any

from alembic.autogenerate.api import AutogenContext
from sqlalchemy import JSON, create_engine, pool

from alembic import context
from app.core.config import load_settings
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.types import UTCDateTime

config = context.config
target_metadata = Base.metadata
url = load_settings().database_url


def _render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | bool:
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    if type_ == "type" and isinstance(obj, JSON):
        return "sa.JSON()"
    return False


if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_item=_render_item
        )
        with context.begin_transaction():
            context.run_migrations()
