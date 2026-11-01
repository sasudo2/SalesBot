from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import DateTime, String, Uuid, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class ConversationRecord(Base):
    __tablename__="ConversationRecords"
    conversation_id : Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    last_activity_at : Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default = lambda: datetime.now(timezone.utc),
    )
    conversation_history: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, default = list,
    )


