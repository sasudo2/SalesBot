from sqlalchemy.orm import Session

from app.core.hashing import sha256_hex
from app.domain.enums import KnowledgeSource
from app.domain.models import KnowledgeChunk, Product
from app.rag.base import Embedder
from app.rag.chunking import chunk_text
from app.rag.embedding import embed_texts
from app.repo.knowledge import upsert_chunk
from app.repo.product import get_product_by_id, upsert_product


def product_embedding_text(p: Product) -> str:
    return f"{p.name}. {p.description}. Aliases: {', '.join(p.aliases)}. Tags: {', '.join(p.tags)}"


def ingest_products(
    db: Session, embedder: Embedder, products: list[Product], embedding_model: str
) -> int:
    pending: list[Product] = []
    for product in products:
        product.embedding_hash = sha256_hex(product_embedding_text(product) + "|" + embedding_model)
        stored = get_product_by_id(db, product.id)
        if stored and stored.embedding_hash == product.embedding_hash:
            product.embedding = stored.embedding
        else:
            pending.append(product)
    vectors = embed_texts(embedder, [product_embedding_text(p) for p in pending])
    for product, vector in zip(pending, vectors, strict=True):
        product.embedding = vector
    for product in products:
        upsert_product(db, product)
    return len(products)


def ingest_knowledge(
    db: Session,
    embedder: Embedder,
    docs: list[tuple[KnowledgeSource, str, str]],
    max_chars: int = 800,
    overlap: int = 100,
) -> int:
    chunks = [
        KnowledgeChunk(source=source, title=f"{title} #{n}", text=part)
        for source, title, text in docs
        for n, part in enumerate(chunk_text(text, max_chars, overlap), 1)
    ]
    vectors = embed_texts(embedder, [c.text for c in chunks])
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk.embedding = vector
        upsert_chunk(db, chunk)
    return len(chunks)
