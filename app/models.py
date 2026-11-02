from pydantic import BaseModel
from uuid import UUID, uuid4
from collections.abc import Callable

class Query(BaseModel):
    query: str
    conversation_id: UUID

class ToolSpec(BaseModel):
    name: str
    description : str
    parameters : dict

class ToolCalls(BaseModel):
    id: str
    name: str
    arguments: dict

class Usage(BaseModel):
    input_token: int = 0
    ouput_taken: int = 0

class LLMResponse(BaseModel):
    content: str
    tool_calls: list[ToolCalls] = []
    usage: Usage

class Response(BaseModel):
    response: str
    conversation_id: UUID