from openai import OpenAI, OpenAIError

from app.domain.errors import ProviderError


class OpenAIEmbedder:
    name = "openai"

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        try:
            for start in range(0, len(texts), 100):
                response = self.client.embeddings.create(
                    model=self.model, input=texts[start : start + 100]
                )
                vectors.extend(d.embedding for d in sorted(response.data, key=lambda d: d.index))
        except OpenAIError as exc:
            raise ProviderError("Embedding request failed") from exc
        if len(vectors) != len(texts):
            raise ProviderError("Embedding provider returned an incorrect number of vectors")
        return vectors
