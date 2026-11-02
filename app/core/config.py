from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", case_sensitive=False, env_ignore_empty=True
    )

    app_env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "sqlite:///./sales_agent.db"
    default_provider: str = "openai"
    fallback_providers: list[str] = []
    enable_fake_provider: bool = False
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-5-5"
    embedding_model: str = "text-embedding-3-small"
    provider_timeout_s: float = 30.0
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1024
    max_agent_iterations: int = 6
    history_window: int = 30
    summary_threshold: int = 60
    summary_batch: int = 10
    cart_ttl_minutes: int = 60
    expire_job_interval_s: int = 300
    semantic_weight: float = 0.6
    min_knowledge_score: float = 0.25
    currency: str = "NPR"
    shop_name: str = "Himal Mart"
    handoff_reply: str = "Thank you. A member of our team will reply to you shortly."
    api_key: str | None = None
    cors_origins: list[str] = []
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    server_reload: bool = False
    log_level: Literal["critical", "error", "warning", "info", "debug"] = "info"


@lru_cache
def load_settings() -> Settings:
    return Settings()
