from fastapi import FastAPI, Form, Depends, HTTPException
from uuid import UUID, uuid4
from pathlib import Path
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.llm.LLMClient import generate_document_summary, generate_answer

from app.api.authentication import assign_conversation_id, conversation_exits


app = FastAPI()

#create an asynchronus database engine
engine = create_async_engine("sqlite+aiosqlite:///../data/products.db")
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with SessionLocal() as db:
        yield db

@app.post("/prepare")
async def prepare():
    await generate_document_summary(Path("data/shein-products.csv"))
    return "Hello!!"

@app.post("/chat")
async def chat(
    conversation_id: UUID | None = Form(None),
    query: str = None,
    db: AsyncSession = Depends(get_db)
)->str:
    # Check if conversation_id is none, if found none assigne a conversation id
    if conversation_id is None:
        conversation_id = await assign_conversation_id(db)
        #:Introduce it self as AI customer agent
        return {"message": "Hello! I am your AI sales agent. How can I help you with your query and shopping today?"}

    #Check if Conversation_id exists, if found load the conversation history and reply the query
    if conversation_exits(conversation_id):
        #TODO: apply RAG to resolve query
        return await generate_answer(query=query, conversation_id= conversation_id, db = db)
    else:
        #If Conversation_id doesn't exist raise a HTTP error
        raise HTTPException(status_code=404, detail="couldn't find the conversation")
    
