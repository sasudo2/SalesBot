from app.domain.errors import ProviderError
from app.rag.base import Embedder


def embed_texts(embedder: Embedder, texts: list[str]) -> list[list[float]]:
    nonblank = [text for text in texts if text.strip()]
    vectors = embedder.embed(nonblank) if nonblank else []
    if len(vectors) != len(nonblank):
        raise ProviderError("Embedding provider returned an incorrect number of vectors")
    iterator = iter(vectors)
    return [next(iterator) if text.strip() else [] for text in texts]
