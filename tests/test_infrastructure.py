import logging
import sys
import threading
from unittest.mock import Mock, patch

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.api.deps import (
    _llm_register,
    get_db,
    get_embedder,
    get_llm_register,
    get_settings,
    get_tool_registry,
)
from app.core.config import Settings, load_settings
from app.db.base import Base
from app.db.init import init_db
from app.db.models import ProductORM
from app.db.session import get_engine, get_sessionmaker
from app.domain.errors import ProviderError
from app.domain.models import Product
from app.repo.product import upsert_product
from app.services.jobs import run_expiry_once


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'runtime.db'}")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("EXPIRE_JOB_INTERVAL_S", "0")
    load_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    yield load_settings()
    get_engine().dispose()
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()
    load_settings.cache_clear()
    _llm_register.cache_clear()


def test_real_session_dependency(runtime):
    init_db()
    assert get_settings() is load_settings()
    generator = get_db()
    db = next(generator)
    upsert_product(db, Product(id="p", sku="p", name="P", price="10.00"))
    with pytest.raises(RuntimeError, match="abort"):
        generator.throw(RuntimeError("abort"))
    with get_sessionmaker()() as other:
        assert other.get(ProductORM, "p") is None
    generator = get_db()
    next(generator)
    generator.close()
    assert run_expiry_once() == 0
    assert get_engine() is get_engine()


def test_provider_dependencies():
    settings = Settings(
        _env_file=None,
        app_env="test",
        default_provider="fake",
        openai_api_key="test-openai",
        anthropic_api_key="test-anthropic",
    )
    with (
        patch("app.api.deps.OpenAIProvider") as openai,
        patch("app.api.deps.AnthropicProvider") as anthropic,
        patch("app.api.deps.OpenAIEmbedder") as embedder,
    ):
        register = get_llm_register(settings)
        assert register is get_llm_register(settings)
        register._get("openai")
        register._get("anthropic")
        register._get("fake")
        openai.assert_called_once()
        anthropic.assert_called_once()
        assert get_embedder(settings) is embedder.return_value
    with pytest.raises(RuntimeError, match="default"):
        get_llm_register(Settings(_env_file=None, default_provider="missing"))
    with pytest.raises(ProviderError, match="required"):
        get_embedder(Settings(_env_file=None, openai_api_key=None))
    assert get_tool_registry() is get_tool_registry()
    _llm_register.cache_clear()


def test_cli(runtime, monkeypatch, fake_embedder, caplog):
    from app import cli

    monkeypatch.setattr(sys, "argv", ["cli", "init-db"])
    with caplog.at_level(logging.INFO):
        cli._main()
    monkeypatch.setattr(cli, "get_embedder", lambda settings: fake_embedder)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli",
            "ingest",
            "--products",
            "data/sample/products.csv",
            "--knowledge",
            "data/sample/knowledge",
        ],
    )
    with caplog.at_level(logging.INFO):
        cli._main()
    assert "Wrote 18 rows" in caplog.text
    with Session(get_engine()) as db:
        assert len(list(db.scalars(select(ProductORM)))) == 12


def test_lifespan_and_cors(runtime, monkeypatch):
    import app.main as main

    runtime.expire_job_interval_s = 1
    runtime.cors_origins = ["http://shop.test"]
    monkeypatch.setattr(main, "load_settings", lambda: runtime)
    started = threading.Event()

    def fail_job():
        started.set()
        raise RuntimeError("test background failure")

    monkeypatch.setattr(main, "run_expiry_once", fail_job)
    with TestClient(main.create_app()) as client:
        assert started.wait(timeout=3)
        response = client.options(
            "/chat",
            headers={
                "Origin": "http://shop.test",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.headers["Access-Control-Allow-Origin"] == "http://shop.test"
        assert client.get("/health").status_code == 200
    runtime.app_env = "prod"
    runtime.expire_job_interval_s = 0
    initialize = Mock()
    monkeypatch.setattr(main, "init_db", initialize)
    with TestClient(main.create_app()) as client:
        assert client.get("/health").status_code == 200
    initialize.assert_not_called()


def test_delivery_configuration():
    from pathlib import Path

    compose = yaml.safe_load(Path("docker-compose.yml").read_text())
    assert compose["services"]["db"]["image"] == "postgres:16"
    assert "alembic upgrade head && uvicorn app.main:app" in compose["services"]["api"]["command"]
    dockerfile = Path("Dockerfile").read_text()
    assert "USER app" in dockerfile and '"uvicorn", "app.main:app"' in dockerfile
    assert "--reload" not in dockerfile
    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table.name}" in ddl
    assert "JSONB" in str(CreateTable(ProductORM.__table__).compile(dialect=dialect))
