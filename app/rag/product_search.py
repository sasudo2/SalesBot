from sqlalchemy.orm import Session

from app.domain.models import ProductHit
from app.rag.base import Embedder
from app.rag.embedding import embed_texts
from app.rag.similarity import cosine_similarity, lexical_score
from app.repo.product import list_active_products


def search_products_hybrid(
    db: Session, embedder: Embedder, query: str, limit: int = 5, semantic_weight: float = 0.6
) -> list[ProductHit]:
    vector = embed_texts(embedder, [query])[0]
    hits: list[ProductHit] = []
    for product in list_active_products(db):
        semantic = max(0.0, cosine_similarity(vector, product.embedding or []))
        score = semantic_weight * semantic + (1 - semantic_weight) * lexical_score(query, product)
        if score > 0:
            hits.append(ProductHit(product=product, score=score, available=product.available))
    return sorted(hits, key=lambda h: (-h.score, h.product.name))[:limit]
