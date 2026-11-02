from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.db.models import CartItemORM, CartORM, ConversationORM, MessageORM
from app.db.types import UTCDateTime
from app.domain.enums import KnowledgeSource, MessageRole
from app.domain.errors import ConflictError, NotFoundError
from app.domain.models import CartItem, KnowledgeChunk, Message
from app.repo.conversation import create_conversation, get_conversation, save_conversation
from app.repo.knowledge import list_chunks, upsert_chunk
from app.repo.product import get_product_by_id, list_active_products


def test_repo_conversation(db):
    id_ = uuid4()
    assert get_conversation(db, id_) is None
    conversation = create_conversation(db, id_)
    conversation.messages = [Message(role=MessageRole.user, content="hello")]
    cart = conversation.ensure_cart()
    cart.items = [CartItem(product_id="p", name="P", quantity=2, unit_price="10.00")]
    conversation = save_conversation(db, conversation)
    first_version = conversation.version
    db.commit()
    assert get_conversation(db, id_).messages[0].content == "hello"
    conversation = save_conversation(db, conversation)
    assert conversation.version > first_version
    assert len(list(db.scalars(select(MessageORM)))) == 1
    conversation.cart.items[0].quantity = 3
    conversation = save_conversation(db, conversation)
    assert db.scalar(select(CartItemORM)).quantity == 3
    conversation.cart.items = []
    conversation = save_conversation(db, conversation)
    assert not list(db.scalars(select(CartItemORM)))
    conversation.cart = None
    assert save_conversation(db, conversation).cart is None
    with pytest.raises(NotFoundError):
        save_conversation(db, conversation.model_copy(update={"conversation_id": uuid4()}))


def test_repo_conflict(db, engine):
    conversation = create_conversation(db, uuid4())
    db.commit()
    with Session(engine) as other:
        stale = get_conversation(other, conversation.conversation_id)
        other.rollback()
        conversation = save_conversation(db, conversation)
        db.commit()
        with pytest.raises(ConflictError):
            save_conversation(other, stale)
    assert db.get(ConversationORM, conversation.conversation_id).version == conversation.version


def test_product_and_knowledge(db, seed_products):
    assert len(list_active_products(db)) == 2
    assert get_product_by_id(db, "missing") is None
    chunk = KnowledgeChunk(source=KnowledgeSource.faq, title="Hours", text="Nine to five")
    first = upsert_chunk(db, chunk)
    assert upsert_chunk(db, chunk).version == first.version
    chunk.text = "Eight to six"
    assert upsert_chunk(db, chunk).version == first.version + 1
    assert len(list_chunks(db, KnowledgeSource.faq)) == 1
    assert len(list_chunks(db)) == 1


def test_utc_type(db):
    type_ = UTCDateTime()
    dialect = db.get_bind().dialect
    naive = datetime(2026, 1, 1)
    assert type_.process_bind_param(naive, dialect).tzinfo == UTC
    assert type_.process_bind_param(naive.replace(tzinfo=UTC), dialect).tzinfo == UTC
    assert type_.process_result_value(naive, dialect).tzinfo == UTC
    assert type_.process_result_value(None, dialect) is None
    assert type_.process_bind_param(None, dialect) is None


def test_stale_cart_version(db):
    conversation = create_conversation(db, uuid4())
    conversation.ensure_cart()
    conversation = save_conversation(db, conversation)
    db.commit()
    conversation = get_conversation(db, conversation.conversation_id)
    assert conversation.conversation_id in db.info["_conversation_refs"]
    db.execute(
        update(CartORM)
        .where(CartORM.conversation_id == conversation.conversation_id)
        .values(version=CartORM.version + 1)
        .execution_options(synchronize_session=False)
    )
    conversation.cart.updated_at = utcnow()
    with pytest.raises(ConflictError, match="modified"):
        save_conversation(db, conversation)
    db.rollback()
