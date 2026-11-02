from unittest.mock import Mock, patch

import pytest

from app.api.deps import _local_embedder, get_embedder
from app.core.config import Settings
from app.domain.errors import ProviderError
from app.rag.local_embedder import LocalEmbedder


def test_local_embeddings_are_lazy_and_cached():
    with patch("app.rag.local_embedder.TextEmbedding") as factory:
        factory.return_value.embed.return_value = [Mock(tolist=lambda: [0.1, 0.2])]
        embedder = LocalEmbedder("test-model")
        factory.assert_not_called()
        assert embedder.embed([]) == []
        assert embedder.embed(["hello"]) == [[0.1, 0.2]]
        assert embedder.embed(["again"]) == [[0.1, 0.2]]
        factory.assert_called_once_with(model_name="test-model", threads=2)
    _local_embedder.cache_clear()
    settings = Settings(_env_file=None, embedding_provider="local", openai_api_key=None)
    assert get_embedder(settings) is get_embedder(settings)
    _local_embedder.cache_clear()


def test_local_embedding_failure():
    with (
        patch("app.rag.local_embedder.TextEmbedding", side_effect=RuntimeError("download failed")),
        pytest.raises(ProviderError, match="Local embedding failed"),
    ):
        LocalEmbedder("test").embed(["hello"])
    with patch("app.rag.local_embedder.TextEmbedding") as factory:
        factory.return_value.embed.return_value = []
        with pytest.raises(ProviderError, match="incorrect"):
            LocalEmbedder("test").embed(["hello"])


@pytest.mark.parametrize(
    ("provider", "expected_model"),
    [("local", "BAAI/bge-small-en-v1.5"), ("openai", "text-embedding-3-small")],
)
def test_cli_hashes_with_selected_embedding_model(
    tmp_path, monkeypatch, db, fake_embedder, settings, provider, expected_model
):
    import sys

    from app import cli

    products = tmp_path / "products.csv"
    products.write_text(
        "id,sku,name,description,price,currency,stock_on_hand,aliases,tags\n"
        "p,p,Shirt,Cotton shirt,10.00,USD,0,,clothing\n",
        encoding="utf-8",
    )
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    settings.embedding_provider = provider
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(cli, "get_embedder", lambda _: fake_embedder)
    monkeypatch.setattr(cli, "get_sessionmaker", lambda: lambda: db)
    monkeypatch.setattr(
        sys,
        "argv",
        ["cli", "ingest", "--products", str(products), "--knowledge", str(knowledge)],
    )
    with (
        patch("app.cli.ingest_products", return_value=1) as ingest,
        patch("app.cli.ingest_knowledge", return_value=0),
    ):
        cli._main()
    assert ingest.call_args.args[-1] == expected_model
