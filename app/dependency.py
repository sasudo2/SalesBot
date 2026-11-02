from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from collections.abc import AsyncGenerator
from functools import lru_cache

from app.settings import setting
from app.llm import LLMRepository, FakeProvider


DATABASE_URL = setting.database_url

engine = create_async_engine(setting.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

@lru_cache
async def get_llm() -> LLMRepository:
    llm_repository = LLMRepository()
    llm_repository.add_provider("fake_provider", FakeProvider)
    return llm_repository