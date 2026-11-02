from fastapi import FastAPI, Depends, HTTPException
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Query
from app.dependency import init_db, engine, get_db, get_llm
from app.llm import LLMRepository, FakeProvider
from app.helper import handle_query
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.llm = LLMRepository()
    app.state.llm.add_provider("fake_provider", FakeProvider)
    yield
    await engine.dispose()


app=FastAPI(lifespan=lifespan)
logger = logging.getLogger(__name__)

@app.post("/chat")
async def chat(query: Query, db: AsyncSession = Depends(get_db), llm:LLMRepository = Depends(get_llm)):
    try:
        return await handle_query(query, db, llm)
    except ConversationNotFound:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except QueryHandlingError as e:
        logger.exception("Query handling failed")
        raise HTTPException(status_code=502, detail="LLM request failed")