from pathlib import Path

import pytest

from factorylens.config import Settings
from factorylens.vector_store import create_store, get_embeddings


def test_demo_embeddings_remain_offline(tmp_path: Path):
    settings = Settings(data_dir=tmp_path, embedding_provider="demo")
    embeddings = get_embeddings(settings)
    store = create_store(settings)

    assert embeddings.provider_name == "demo-hashing"
    assert store.embedding_provider_name == "demo-hashing"
    assert settings.index_path == tmp_path / "index.json"


def test_semantic_provider_uses_an_isolated_index(tmp_path: Path):
    settings = Settings(
        data_dir=tmp_path,
        embedding_provider="openai",
        openai_embedding_model="text-embedding-3-small",
    )

    assert settings.index_path.name == "index-openai-text-embedding-3-small.json"


def test_openai_embeddings_require_an_api_key(tmp_path: Path):
    settings = Settings(data_dir=tmp_path, embedding_provider="openai", openai_api_key="")

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_embeddings(settings)
