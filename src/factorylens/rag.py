from __future__ import annotations

from factorylens.config import Settings, get_settings
from factorylens.llm import TextGenerator, get_generator
from factorylens.schemas import AskResponse
from factorylens.vector_store import JsonVectorStore, create_store


class RAGService:
    def __init__(
        self,
        settings: Settings | None = None,
        store: JsonVectorStore | None = None,
        generator: TextGenerator | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.store = store or create_store(self.settings)
        self.generator = generator or get_generator(self.settings)

    def ask(self, question: str, top_k: int | None = None) -> AskResponse:
        sources = self.store.similarity_search(question, k=top_k or self.settings.top_k)
        answer = self.generator.answer(question, sources)
        grounded = bool(sources and sources[0].score >= 0.05)
        return AskResponse(
            answer=answer,
            sources=sources,
            grounded=grounded,
            provider=self.generator.provider_name,
        )
