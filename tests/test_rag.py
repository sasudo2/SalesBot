from unittest.mock import Mock

import pytest

from app.domain.enums import KnowledgeSource
from app.domain.errors import ProviderError
from app.domain.models import KnowledgeChunk
from app.rag.chunking import chunk_text
from app.rag.embedding import embed_texts
from app.rag.ingest import ingest_knowledge, ingest_products
from app.rag.knowledge_search import search_knowledge_chunks
from app.rag.product_search import search_products_hybrid
from app.rag.similarity import cosine_similarity, lexical_score
from app.repo.knowledge import upsert_chunk


def test_chunk_and_similarity(seed_products):
    chunks = chunk_text("abcdefghijklm", max_chars=6, overlap=2)
    assert chunks == ["abcdef", "efghij", "ijklm"]
    assert chunk_text("ab\n\ncd\n\nef", 6, 1) == ["ab\n\ncd", "ef"]
    assert chunk_text("a\n\nabcdefghijk", 6, 1)[0] == "a"
    assert chunk_text(" \n\n ") == []
    with pytest.raises(ValueError):
        chunk_text("a", 1, 1)
    assert cosine_similarity([], [1]) == 0
    assert cosine_similarity([0], [1]) == 0
    assert cosine_similarity([1, 0], [1, 0]) == 1
    with pytest.raises(ValueError):
        cosine_similarity([1], [1, 2])
    assert lexical_score("chiura", seed_products[0]) == 1
    assert lexical_score("", seed_products[0]) == 0
    assert lexical_score("zzzz", seed_products[0]) == 0


def test_embedding(fake_embedder):
    assert embed_texts(fake_embedder, ["", "hi", " "])[::2] == [[], []]
    with pytest.raises(ProviderError):
        embed_texts(Mock(embed=Mock(return_value=[])), ["hi"])


def test_search_and_ingest(db, seed_products, fake_embedder):
    hits = search_products_hybrid(db, fake_embedder, "chiura")
    assert hits[0].product.id == "chiura"
    assert search_products_hybrid(db, fake_embedder, "soap")[0].available == 0
    assert search_products_hybrid(db, fake_embedder, "unrelated", semantic_weight=0) == []
    embedder = Mock(wraps=fake_embedder)
    assert ingest_products(db, embedder, seed_products, "test") == 2
    embedder.reset_mock()
    ingest_products(db, embedder, seed_products, "test")
    embedder.embed.assert_not_called()
    assert (
        ingest_knowledge(db, fake_embedder, [(KnowledgeSource.policy, "Hours", "Open daily")]) == 1
    )
    upsert_chunk(db, KnowledgeChunk(source=KnowledgeSource.faq, title="Empty", text="none"))
    assert len(search_knowledge_chunks(db, fake_embedder, "Open daily")) == 1
    assert search_knowledge_chunks(db, fake_embedder, "Open daily", min_score=1.1) == []
