from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import SecretStr

class Settings(BaseSettings):
    app_env: str = "dev"

    openrouter_token: SecretStr
    openrouter_model: str = "nvidia/nemotron-3.5-lightning:free"

    hf_token: SecretStr

    summary_path: Path = Path("data/summary.txt")

    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

setting = Settings()