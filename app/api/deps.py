import secrets
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, load_settings
from app.db.session import get_sessionmaker
from app.domain.enums import ToolErrorCode
from app.domain.errors import AppError, ProviderError
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.fake_provider import FakeProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.register import LLMProviderRegister
from app.rag.base import Embedder
from app.rag.openai_embedder import OpenAIEmbedder
from app.tools import build_tool_registry
from app.tools.registry import ToolRegistry


def get_settings() -> Settings:
    return load_settings()


def get_db() -> Iterator[Session]:
    db = get_sessionmaker()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@lru_cache
def _llm_register(settings_json: str) -> LLMProviderRegister:
    settings = Settings.model_validate_json(settings_json)
    register = LLMProviderRegister(settings.default_provider, settings.fallback_providers)
    if settings.openai_api_key:
        register.register(
            "openai",
            lambda: OpenAIProvider(
                settings.openai_api_key or "", settings.openai_model, settings.provider_timeout_s
            ),
        )
    if settings.anthropic_api_key:
        register.register(
            "anthropic",
            lambda: AnthropicProvider(
                settings.anthropic_api_key or "",
                settings.anthropic_model,
                settings.provider_timeout_s,
            ),
        )
    if settings.enable_fake_provider or settings.app_env == "test":
        register.register("fake", lambda: FakeProvider([]))
    if settings.default_provider not in register._factories:
        raise RuntimeError("The default LLM provider is not configured")
    return register


def get_llm_register(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMProviderRegister:
    return _llm_register(settings.model_dump_json())


def get_embedder(settings: Annotated[Settings, Depends(get_settings)]) -> Embedder:
    if not settings.openai_api_key:
        raise ProviderError("An OpenAI API key is required for embeddings")
    return OpenAIEmbedder(settings.openai_api_key, settings.embedding_model)


@lru_cache
def get_tool_registry() -> ToolRegistry:
    return build_tool_registry()


def require_api_key(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    supplied = request.headers.get("X-API-Key", "")
    if settings.api_key and not secrets.compare_digest(
        settings.api_key.encode("utf-8"), supplied.encode("utf-8")
    ):
        raise AppError("Invalid API key", code=ToolErrorCode.invalid_state, http_status=401)
