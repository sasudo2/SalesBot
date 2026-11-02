from sqlalchemy.orm import Session

from app.domain.enums import KnowledgeSource
from app.domain.models import KnowledgeHit
from app.rag.base import Embedder
from app.rag.embedding import embed_texts
from app.rag.similarity import cosine_similarity
from app.repo.knowledge import list_chunks


def search_knowledge_chunks(
    db: Session,
    embedder: Embedder,
    query: str,
    source: KnowledgeSource | None = None,
    limit: int = 3,
    min_score: float = 0.25,
) -> list[KnowledgeHit]:
    vector = embed_texts(embedder, [query])[0]
    hits: list[KnowledgeHit] = []
    for chunk in list_chunks(db, source):
        if chunk.embedding:
            score = cosine_similarity(vector, chunk.embedding)
            if score >= min_score:
                hits.append(KnowledgeHit(chunk=chunk, score=score))
    return sorted(hits, key=lambda h: -h.score)[:limit]
