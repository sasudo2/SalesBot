from datetime import datetime

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base
from app.db.types import JsonType, tz_datetime


class KnowledgeChunkORM(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("source", "title"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(JsonType)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = tz_datetime(onupdate=utcnow)
