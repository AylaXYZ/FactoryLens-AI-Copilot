from __future__ import annotations

from typing import Protocol

from factorylens.config import Settings
from factorylens.schemas import SourceChunk


class TextGenerator(Protocol):
    provider_name: str

    def answer(self, question: str, sources: list[SourceChunk]) -> str: ...


SYSTEM_PROMPT = """你是企业知识库助手。只能依据给定资料回答。
要求：
1. 先给直接结论，再给操作步骤；
2. 每个关键结论以 [1]、[2] 形式标注来源；
3. 资料不足时明确说“当前知识库没有足够依据”，不得编造；
4. 涉及设备安全时提醒停机、断电、挂牌上锁和人工复核。"""


def build_context(sources: list[SourceChunk]) -> str:
    return "\n\n".join(
        f"[{index}] 来源={source.source}"
        + (f" 页码={source.page}" if source.page else "")
        + (f" 工作表={source.sheet}" if source.sheet else "")
        + f"\n{source.content}"
        for index, source in enumerate(sources, start=1)
    )


class DemoGenerator:
    provider_name = "demo-grounded"

    def answer(self, question: str, sources: list[SourceChunk]) -> str:
        if not sources or sources[0].score < 0.05:
            return "当前知识库没有足够依据。请补充相关设备手册、SOP或历史故障案例。"
        points = []
        for index, source in enumerate(sources[:3], start=1):
            text = source.content.replace("\n", " ").strip()
            points.append(f"- {text[:170]}{'…' if len(text) > 170 else ''} [{index}]")
        safety = ""
        if any(word in question for word in ("故障", "维修", "温度", "振动", "报警")):
            safety = "\n\n安全提示：执行维修前请停机、断电并挂牌上锁，由授权人员复核。"
        return "根据知识库，建议先按以下证据核查：\n\n" + "\n".join(points) + safety


class LangChainGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.llm_provider == "openai":
            from langchain_openai import ChatOpenAI

            self.provider_name = f"openai-compatible:{settings.openai_model}"
            self.model = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                temperature=0,
            )
        elif settings.llm_provider == "ollama":
            from langchain_ollama import ChatOllama

            self.provider_name = f"ollama:{settings.ollama_model}"
            self.model = ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=0,
            )
        else:
            raise ValueError(f"Unsupported provider: {settings.llm_provider}")

    def answer(self, question: str, sources: list[SourceChunk]) -> str:
        if not sources:
            return "当前知识库没有足够依据。"
        messages = [
            ("system", SYSTEM_PROMPT),
            ("human", f"问题：{question}\n\n知识库资料：\n{build_context(sources)}"),
        ]
        response = self.model.invoke(messages)
        return str(response.content)


def get_generator(settings: Settings) -> TextGenerator:
    if settings.llm_provider == "demo":
        return DemoGenerator()
    return LangChainGenerator(settings)

