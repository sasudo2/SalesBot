from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.agent.chat import handle_query
from app.api.deps import (
    get_db,
    get_embedder,
    get_llm_register,
    get_settings,
    get_tool_registry,
    require_api_key,
)
from app.api.schemas import ChatRequest, ChatResponse
from app.core.config import Settings
from app.llm.register import LLMProviderRegister
from app.rag.base import Embedder
from app.tools.registry import ToolRegistry

router = APIRouter()


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
def chat_endpoint(
    body: ChatRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    llm: Annotated[LLMProviderRegister, Depends(get_llm_register)],
    tools: Annotated[ToolRegistry, Depends(get_tool_registry)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChatResponse:
    return handle_query(body, db, llm, tools, embedder, settings, request.state.request_id)
