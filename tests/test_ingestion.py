from pathlib import Path

import pandas as pd
from docx import Document as DocxDocument

from factorylens.ingestion import load_and_chunk, load_document


def test_load_markdown_and_chunk(tmp_path: Path):
    path = tmp_path / "manual.md"
    path.write_text("# 手册\n电机温度超过 90°C 时应停机。", encoding="utf-8")
    documents = load_document(path)
    chunks = load_and_chunk([path])
    assert "90°C" in documents[0].page_content
    assert chunks[0].metadata["source"] == "manual.md"
    assert chunks[0].metadata["chunk_id"]


def test_load_docx_and_xlsx(tmp_path: Path):
    docx_path = tmp_path / "sop.docx"
    doc = DocxDocument()
    doc.add_paragraph("维修前执行挂牌上锁")
    doc.save(docx_path)

    xlsx_path = tmp_path / "cases.xlsx"
    pd.DataFrame([{"报警码": "E-01", "处置": "检查风扇"}]).to_excel(
        xlsx_path, index=False, sheet_name="案例"
    )

    docx_docs = load_document(docx_path)
    xlsx_docs = load_document(xlsx_path)
    assert "挂牌上锁" in docx_docs[0].page_content
    assert "E-01" in xlsx_docs[0].page_content
    assert xlsx_docs[0].metadata["sheet"] == "案例"

