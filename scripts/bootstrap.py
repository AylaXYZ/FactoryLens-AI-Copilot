from pathlib import Path

from factorylens.config import get_settings
from factorylens.ingestion import load_and_chunk
from factorylens.vector_store import create_store

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    settings = get_settings()
    store = create_store(settings)
    paths = list((ROOT / "knowledge_base").glob("*"))
    chunks = load_and_chunk(paths)
    added = store.add_documents(chunks)
    print(f"Knowledge base ready: {len(paths)} files, {len(chunks)} chunks, {added} added.")


if __name__ == "__main__":
    main()
