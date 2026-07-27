from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class SourceChunk(BaseModel):
    chunk_id: str
    source: str
    page: int | None = None
    sheet: str | None = None
    content: str
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=10)


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    grounded: bool
    provider: str


class SensorEvent(BaseModel):
    asset_id: str
    asset_name: str = "包装线伺服电机"
    temperature_c: float = 86.0
    vibration_mm_s: float = 8.1
    error_code: str = "E-OVHT-07"
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: str = ""


class WorkOrder(BaseModel):
    work_order_id: str = Field(default_factory=lambda: f"WO-{uuid4().hex[:8].upper()}")
    asset_id: str
    title: str
    priority: Literal["P1", "P2", "P3", "P4"]
    suspected_cause: str
    recommended_actions: list[str]
    safety_notice: str
    evidence: list[SourceChunk]
    status: Literal["draft", "approved", "closed"] = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DiagnosisResult(BaseModel):
    anomaly: bool
    severity: Literal["normal", "warning", "critical"]
    rationale: str
    work_order: WorkOrder | None = None
    workflow_trace: list[str]


class ProductionRecord(BaseModel):
    date: str
    line: str
    planned_qty: int
    actual_qty: int
    downtime_minutes: int
    alarms: int


class ProductionReport(BaseModel):
    title: str
    summary: str
    plan_attainment: float
    total_downtime_minutes: int
    alarm_count: int
    risks: list[str]
    actions: list[str]

