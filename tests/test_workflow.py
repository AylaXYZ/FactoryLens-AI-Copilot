from pathlib import Path

from langchain_core.documents import Document

from factorylens.config import Settings
from factorylens.ingestion import chunk_documents
from factorylens.schemas import SensorEvent
from factorylens.vector_store import JsonVectorStore
from factorylens.workflow import MaintenanceWorkflow


def test_anomaly_creates_draft_work_order(tmp_path: Path):
    settings = Settings(data_dir=tmp_path)
    store = JsonVectorStore(settings.index_path)
    store.add_documents(
        chunk_documents(
            [
                Document(
                    page_content="温度过高时检查风扇、风道和轴承，维修前执行挂牌上锁。",
                    metadata={"source": "manual.md"},
                )
            ]
        )
    )
    result = MaintenanceWorkflow(settings=settings, store=store).run(
        SensorEvent(
            asset_id="M-01",
            temperature_c=92,
            vibration_mm_s=8.2,
            error_code="E-OVHT-07",
        )
    )
    assert result.anomaly
    assert result.severity == "critical"
    assert result.work_order is not None
    assert result.work_order.priority == "P1"
    assert result.work_order.status == "draft"
    assert result.workflow_trace == [
        "detect_anomaly",
        "retrieve_knowledge",
        "reason_root_cause",
        "create_work_order",
    ]
    assert settings.work_order_path.exists()


def test_normal_event_does_not_create_work_order(tmp_path: Path):
    settings = Settings(data_dir=tmp_path)
    result = MaintenanceWorkflow(
        settings=settings, store=JsonVectorStore(settings.index_path)
    ).run(
        SensorEvent(
            asset_id="M-02",
            temperature_c=55,
            vibration_mm_s=2.0,
            error_code="",
        )
    )
    assert not result.anomaly
    assert result.work_order is None
    assert result.workflow_trace == ["detect_anomaly", "finish_normal"]

