from uuid import UUID, uuid4
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.state.conversation_state import ConversationRecord

async def assign_conversation_id(db: AsyncSession) -> UUID:
    new_id = uuid4()
    db_record = ConversationRecord(
        conversation_id=new_id
    )

    db.add(db_record)
    await db.commit()
    await db.refresh(db_record)

    return new_id


async def conversation_exits(
    db: AsyncSession, 
    conversation_id: UUID
    )->bool:
    result = await db.execute(
        select(ConversationRecord).where(ConversationRecord.conversation_id == conversation_id)
    )

    record = result.scalar_one_or_none()
    return record is not None
