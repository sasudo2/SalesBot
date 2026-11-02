from collections.abc import AsyncGenerator

from app.models import Query, Response
from app.llm import LLMRepository


async def handle_query(
        query: Query, 
        db: AsyncGenerator, 
        llm: LLMRepository
        )->Response:
    pass
