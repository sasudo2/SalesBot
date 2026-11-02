import logging

from fastembed import TextEmbedding

from app.domain.errors import ProviderError

logger = logging.getLogger(__name__)


class LocalEmbedder:
    name = "local"

    def __init__(self, model: str) -> None:
        self.model = model
        self._encoder: TextEmbedding | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            if self._encoder is None:
                self._encoder = TextEmbedding(model_name=self.model, threads=2)
            vectors = [vector.tolist() for vector in self._encoder.embed(texts, batch_size=32)]
        except Exception as exc:
            logger.error("Local embedding failed (%s)", type(exc).__name__)
            raise ProviderError(
                "Local embedding failed. Check model availability, download access, "
                "and the FastEmbed model cache."
            ) from exc
        if len(vectors) != len(texts):
            raise ProviderError("Local embedder returned an incorrect number of vectors")
        return vectors
