import hashlib
import sqlite3
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.db import models  # noqa: F401
from app.db.base import Base
from app.domain.models import Product
from app.repo.product import upsert_product


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def connect(connection, _):
        assert isinstance(connection, sqlite3.Connection)
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "begin")
    def begin(connection):
        connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def settings():
    return Settings(
        _env_file=None, app_env="test", default_provider="fake", expire_job_interval_s=0
    )


class _FakeEmbedder:
    name = "test"

    def embed(self, texts):
        return [
            [byte / 255.0 for byte in hashlib.sha256(text.encode()).digest()[:16]] for text in texts
        ]


@pytest.fixture
def fake_embedder():
    return _FakeEmbedder()


@pytest.fixture
def seed_products(db, fake_embedder):
    products = [
        Product(
            id="chiura",
            sku="C1",
            name="Beaten rice",
            aliases=["chiura"],
            tags=["groceries"],
            price=Decimal("125.00"),
            stock_on_hand=10,
        ),
        Product(
            id="soap",
            sku="S1",
            name="Soap",
            price=Decimal("40.00"),
            stock_on_hand=0,
        ),
    ]
    for product in products:
        product.embedding = fake_embedder.embed([product.name])[0]
        upsert_product(db, product)
    db.commit()
    return products


@pytest.fixture
def script():
    from app.llm.fake_provider import FakeProvider

    return lambda *responses: FakeProvider(list(responses))


@pytest.fixture
def fake_llm(script):
    return script()


@pytest.fixture
def client(db, settings, fake_embedder, fake_llm, monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as main
    from app.api.deps import get_db, get_embedder, get_llm_register, get_settings
    from app.llm.register import LLMProviderRegister

    monkeypatch.setattr(main, "load_settings", lambda: settings)
    monkeypatch.setattr(main, "init_db", lambda: None)
    application = main.create_app()
    llm = LLMProviderRegister("fake", [])
    llm.register("fake", lambda: fake_llm)

    def database():
        try:
            yield db
        except Exception:
            db.rollback()
            raise

    application.dependency_overrides.update(
        {
            get_db: database,
            get_settings: lambda: settings,
            get_embedder: lambda: fake_embedder,
            get_llm_register: lambda: llm,
        }
    )
    with TestClient(application, raise_server_exceptions=False) as test_client:
        yield test_client
