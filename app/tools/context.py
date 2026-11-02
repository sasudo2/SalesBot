from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.models import Conversation
from app.rag.base import Embedder


@dataclass
class ToolContext:
    db: Session
    conversation: Conversation
    embedder: Embedder
    settings: Settings
    request_id: str
