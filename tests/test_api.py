from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_db
from app.db.models import ConversationORM, ToolCallLogORM
from app.domain.enums import MessageRole
from app.domain.models import ToolCall
from app.llm.types import LLMResponse
from app.repo.conversation import create_conversation, get_conversation, save_conversation


def _body(id_=None):
    return {"conversation_id": str(id_ or uuid4()), "query": "hello", "channel": "web"}


def test_api(client, fake_llm):
    health = client.get("/health")
    assert health.status_code == 200 and health.json() == {"status": "ok", "db": True}
    assert health.headers["X-Request-ID"]
    fake_llm.script.append(LLMResponse(content="Hello"))
    response = client.post("/chat", json=_body(), headers={"X-Request-ID": "my-request"})
    assert response.status_code == 200, response.text
    assert response.json()["reply"] == "Hello"
    assert response.headers["X-Request-ID"] == "my-request"


@pytest.mark.parametrize("body", [None, {}, {"conversation_id": "bad", "query": ""}])
def test_validation(client, body):
    response = client.post("/chat", json=body)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "invalid_args"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_api_key(client, settings, fake_llm):
    settings.api_key = "test-key"
    assert client.post("/chat", json=_body()).status_code == 401
    assert client.post("/chat", json=_body(), headers={"X-API-Key": "wrong"}).status_code == 401
    fake_llm.script.append(LLMResponse(content="ok"))
    assert client.post("/chat", json=_body(), headers={"X-API-Key": "test-key"}).status_code == 200


def test_api_rollback(client, db, seed_products, fake_llm):
    fake_llm.script.append(
        LLMResponse(
            tool_calls=[
                ToolCall(
                    id="1", name="add_to_cart", arguments={"product_id": "chiura", "quantity": 2}
                )
            ]
        )
    )
    response = client.post("/chat", json=_body())
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "provider_error"
    assert not list(db.scalars(select(ConversationORM)))
    assert not list(db.scalars(select(ToolCallLogORM)))


def test_api_handoff(client, db, fake_llm, settings):
    c = create_conversation(db, uuid4())
    c.handoff = True
    c = save_conversation(db, c)
    db.commit()
    response = client.post("/chat", json=_body(c.conversation_id))
    assert response.status_code == 200
    assert response.json()["reply"] == settings.handoff_reply
    assert response.json()["handoff"] is True
    assert fake_llm.calls == []
    assert get_conversation(db, c.conversation_id).messages[-1].role == MessageRole.assistant


def test_unexpected_error(client, monkeypatch):
    import app.api.chat as chat

    def fail(*args):
        raise RuntimeError("private implementation detail")

    monkeypatch.setattr(chat, "handle_query", fail)
    response = client.post("/chat", json=_body())
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "private" not in response.text
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_health_failure(client):
    db = Mock()
    db.execute.side_effect = SQLAlchemyError("disconnected")
    client.app.dependency_overrides[get_db] = lambda: db
    response = client.get("/health")
    assert response.status_code == 503 and response.json() == {"status": "degraded", "db": False}
    db.rollback.assert_called_once()
