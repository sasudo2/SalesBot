from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Dialect, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import MappedColumn, mapped_column

from app.core.time import utcnow

JsonType = JSON().with_variant(JSONB(), "postgresql")


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


def tz_datetime(**kw: Any) -> MappedColumn[datetime]:
    return mapped_column(UTCDateTime(), default=utcnow, **kw)
