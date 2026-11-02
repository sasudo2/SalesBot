from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.db.models import KnowledgeChunkORM
from app.domain.enums import KnowledgeSource
from app.domain.models import KnowledgeChunk


def list_chunks(db: Session, source: KnowledgeSource | None = None) -> list[KnowledgeChunk]:
    statement = select(KnowledgeChunkORM)
    if source is not None:
        statement = statement.where(KnowledgeChunkORM.source == source.value)
    return [KnowledgeChunk.model_validate(orm) for orm in db.scalars(statement)]


def upsert_chunk(db: Session, chunk: KnowledgeChunk) -> KnowledgeChunk:
    orm = db.scalar(
        select(KnowledgeChunkORM).where(
            KnowledgeChunkORM.source == chunk.source.value, KnowledgeChunkORM.title == chunk.title
        )
    )
    if orm is None:
        orm = KnowledgeChunkORM(source=chunk.source.value, title=chunk.title, version=1)
        db.add(orm)
    elif orm.text != chunk.text:
        orm.version += 1
    orm.text, orm.embedding, orm.updated_at = chunk.text, chunk.embedding, utcnow()
    db.flush()
    return KnowledgeChunk.model_validate(orm)
