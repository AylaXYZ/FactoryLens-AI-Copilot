from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException

from factorylens.config import get_settings
from factorylens.ingestion import load_and_chunk
from factorylens.rag import RAGService
from factorylens.reporting import build_production_report
from factorylens.schemas import (
    AskRequest,
    AskResponse,
    DiagnosisResult,
    ProductionRecord,
    ProductionReport,
    SensorEvent,
)
from factorylens.vector_store import JsonVectorStore
from factorylens.workflow import MaintenanceWorkflow

settings = get_settings()
store = JsonVectorStore(settings.index_path)
rag = RAGService(settings=settings, store=store)
workflow = MaintenanceWorkflow(settings=settings, store=store)

app = FastAPI(
    title="FactoryLens AI Copilot API",
    version="0.1.0",
    description="Enterprise knowledge QA, maintenance diagnosis and production reporting.",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "documents": store.count, "provider": rag.generator.provider_name}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    return rag.ask(request.question, request.top_k)


@app.post("/diagnose", response_model=DiagnosisResult)
def diagnose(event: SensorEvent) -> DiagnosisResult:
    return workflow.run(event)


@app.post("/reports/production", response_model=ProductionReport)
def report(records: list[ProductionRecord]) -> ProductionReport:
    try:
        return build_production_report(records)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/admin/ingest")
def ingest(paths: list[str]) -> dict:
    safe_paths = [Path(item) for item in paths]
    for path in safe_paths:
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
    chunks = load_and_chunk(safe_paths)
    return {"files": len(safe_paths), "chunks": len(chunks), "added": store.add_documents(chunks)}


def run() -> None:
    uvicorn.run("factorylens.api:app", host="127.0.0.1", port=8000, reload=False)
