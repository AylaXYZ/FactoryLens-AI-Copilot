from pathlib import Path

from langchain_core.documents import Document

from factorylens.config import Settings
from factorylens.ingestion import chunk_documents
from factorylens.rag import RAGService
from factorylens.vector_store import JsonVectorStore


def build_store(tmp_path: Path) -> JsonVectorStore:
    store = JsonVectorStore(tmp_path / "index.json")
    documents = [
        Document(
            page_content="E-OVHT-07 表示伺服电机温度过高。先停机断电，再检查冷却风扇和风道。",
            metadata={"source": "设备手册.md"},
        ),
        Document(
            page_content="低库存时应创建采购申请并跟踪供应商交期。",
            metadata={"source": "采购SOP.md"},
        ),
    ]
    store.add_documents(chunk_documents(documents))
    return store


def test_retrieval_returns_relevant_source(tmp_path: Path):
    store = build_store(tmp_path)
    results = store.similarity_search("电机 E-OVHT-07 怎么处理", k=1)
    assert results[0].source == "设备手册.md"
    assert results[0].score > 0


def test_rag_answer_has_source(tmp_path: Path):
    settings = Settings(data_dir=tmp_path, llm_provider="demo")
    service = RAGService(settings=settings, store=build_store(tmp_path))
    result = service.ask("电机温度报警怎么处理？")
    assert result.grounded
    assert result.sources
    assert "[1]" in result.answer

