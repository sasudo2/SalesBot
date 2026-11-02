from pydantic_settings import BaseSettings
from pydantic import SecretStr

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./salesbot.db"

    openrouter_api: SecretStr
    openrouter_model: SecretStr

setting = Settings()