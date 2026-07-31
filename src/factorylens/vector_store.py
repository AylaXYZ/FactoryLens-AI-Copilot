from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol

import numpy as np
from langchain_core.documents import Document
from sklearn.feature_extraction.text import HashingVectorizer

from factorylens.config import Settings
from factorylens.schemas import SourceChunk


class EmbeddingProvider(Protocol):
    provider_name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class LocalHashEmbeddings:
    """Deterministic, dependency-light embeddings for an offline portfolio demo.

    The retrieval interface is intentionally provider-neutral, so this class can be
    replaced with OpenAI or Ollama embeddings in a real deployment.
    """

    def __init__(self, dimensions: int = 1024) -> None:
        self.provider_name = "demo-hashing"
        self.vectorizer = HashingVectorizer(
            n_features=dimensions,
            alternate_sign=False,
            norm="l2",
            analyzer="char_wb",
            ngram_range=(2, 4),
            token_pattern=None,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.vectorizer.transform(texts).toarray().astype(float).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class OpenAIEmbeddingProvider:
    provider_name: str

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError as exc:
            raise RuntimeError("Install model dependencies with: pip install -e .[models]") from exc
        self.provider_name = f"openai:{settings.openai_embedding_model}"
        self.model = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.model.embed_query(text)


class OllamaEmbeddingProvider:
    provider_name: str

    def __init__(self, settings: Settings) -> None:
        try:
            from langchain_ollama import OllamaEmbeddings
        except ImportError as exc:
            raise RuntimeError("Install model dependencies with: pip install -e .[models]") from exc
        self.provider_name = f"ollama:{settings.ollama_embedding_model}"
        self.model = OllamaEmbeddings(
            model=settings.ollama_embedding_model,
            base_url=settings.ollama_base_url,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.model.embed_query(text)


class BgeEmbeddingProvider:
    provider_name: str

    def __init__(self, settings: Settings) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install local semantic embeddings with: pip install -e .[semantic]") from exc
        self.provider_name = f"bge:{settings.bge_embedding_model}"
        self.model = SentenceTransformer(settings.bge_embedding_model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True)
        return np.asarray(vectors, dtype=float).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def get_embeddings(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(settings)
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(settings)
    if settings.embedding_provider == "bge":
        return BgeEmbeddingProvider(settings)
    return LocalHashEmbeddings()


class JsonVectorStore:
    """Small persistent vector store designed for transparent local demos."""

    def __init__(self, path: str | Path, embeddings: EmbeddingProvider | None = None) -> None:
        self.path = Path(path)
        self.embeddings = embeddings or LocalHashEmbeddings()
        self._records: list[dict] = []
        self._load()

    @property
    def embedding_provider_name(self) -> str:
        return self.embeddings.provider_name

    @property
    def count(self) -> int:
        return len(self._records)

    def _load(self) -> None:
        if self.path.exists():
            self._records = json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._records, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add_documents(self, documents: list[Document]) -> int:
        if not documents:
            return 0
        vectors = self.embeddings.embed_documents([d.page_content for d in documents])
        existing = {record["metadata"]["chunk_id"] for record in self._records}
        added = 0
        for document, vector in zip(documents, vectors, strict=True):
            chunk_id = document.metadata["chunk_id"]
            if chunk_id in existing:
                continue
            self._records.append(
                {
                    "content": document.page_content,
                    "metadata": document.metadata,
                    "vector": vector,
                }
            )
            added += 1
        self._save()
        return added

    def similarity_search(self, query: str, k: int = 4) -> list[SourceChunk]:
        if not self._records:
            return []
        query_vector = np.asarray(self.embeddings.embed_query(query), dtype=float)
        matrix = np.asarray([record["vector"] for record in self._records], dtype=float)
        dense_scores = matrix @ query_vector

        # A small lexical bonus makes model names/error codes exact and explainable.
        query_tokens = set(re.findall(r"[\w\-]+", query.lower()))
        scored: list[tuple[float, dict]] = []
        for index, record in enumerate(self._records):
            content_tokens = set(re.findall(r"[\w\-]+", record["content"].lower()))
            overlap = len(query_tokens & content_tokens) / max(1, len(query_tokens))
            score = float(0.82 * dense_scores[index] + 0.18 * overlap)
            scored.append((score, record))
        scored.sort(key=lambda item: item[0], reverse=True)

        results = []
        for score, record in scored[:k]:
            metadata = record["metadata"]
            results.append(
                SourceChunk(
                    chunk_id=metadata["chunk_id"],
                    source=metadata["source"],
                    page=metadata.get("page"),
                    sheet=metadata.get("sheet"),
                    content=record["content"],
                    score=round(score, 4),
                    metadata={
                        key: value
                        for key, value in metadata.items()
                        if key not in {"source", "page", "sheet", "chunk_id", "path"}
                    },
                )
            )
        return results

    def clear(self) -> None:
        self._records = []
        self._save()


def create_store(settings: Settings) -> JsonVectorStore:
    return JsonVectorStore(settings.index_path, embeddings=get_embeddings(settings))
