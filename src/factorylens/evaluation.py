from __future__ import annotations

import json
from pathlib import Path

from factorylens.config import get_settings
from factorylens.ingestion import load_and_chunk
from factorylens.rag import RAGService
from factorylens.vector_store import JsonVectorStore


def evaluate(root: Path) -> dict:
    settings = get_settings()
    store = JsonVectorStore(settings.index_path)
    if not store.count:
        store.add_documents(load_and_chunk((root / "knowledge_base").glob("*")))
    service = RAGService(settings=settings, store=store)
    cases = json.loads((root / "eval" / "questions.json").read_text(encoding="utf-8"))
    source_hits = 0
    term_hits = 0
    details = []
    for case in cases:
        result = service.ask(case["question"])
        sources = [item.source for item in result.sources]
        source_hit = case["expected_source"] in sources
        combined = result.answer + " ".join(item.content for item in result.sources)
        term_hit = all(term in combined for term in case["expected_terms"])
        source_hits += int(source_hit)
        term_hits += int(term_hit)
        details.append(
            {"question": case["question"], "source_hit": source_hit, "term_hit": term_hit}
        )
    total = len(cases)
    return {
        "cases": total,
        "retrieval_hit_rate": source_hits / total,
        "term_coverage": term_hits / total,
        "details": details,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    print(json.dumps(evaluate(root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

