from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...
