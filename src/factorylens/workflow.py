from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from factorylens.config import Settings, get_settings
from factorylens.schemas import DiagnosisResult, SensorEvent, SourceChunk, WorkOrder
from factorylens.vector_store import JsonVectorStore


class MaintenanceState(TypedDict, total=False):
    event: SensorEvent
    anomaly: bool
    severity: str
    rationale: str
    evidence: list[SourceChunk]
    suspected_cause: str
    actions: list[str]
    work_order: WorkOrder
    trace: list[str]


class MaintenanceWorkflow:
    """Deterministic guardrails + RAG evidence + a persisted draft work order."""

    def __init__(
        self, settings: Settings | None = None, store: JsonVectorStore | None = None
    ) -> None:
        self.settings = settings or get_settings()
        self.store = store or JsonVectorStore(self.settings.index_path)
        self.graph = self._build_graph()

    @staticmethod
    def _detect(state: MaintenanceState) -> dict:
        event = state["event"]
        critical = event.temperature_c >= 90 or event.vibration_mm_s >= 10
        warning = event.temperature_c >= 75 or event.vibration_mm_s >= 7 or bool(event.error_code)
        severity = "critical" if critical else "warning" if warning else "normal"
        anomaly = severity != "normal"
        rationale = (
            f"温度 {event.temperature_c:.1f}°C，振动 {event.vibration_mm_s:.1f} mm/s，"
            f"报警码 {event.error_code or '无'}；规则判定为 {severity}。"
        )
        return {
            "anomaly": anomaly,
            "severity": severity,
            "rationale": rationale,
            "trace": ["detect_anomaly"],
        }

    @staticmethod
    def _route(state: MaintenanceState) -> str:
        return "retrieve" if state["anomaly"] else "finish_normal"

    def _retrieve(self, state: MaintenanceState) -> dict:
        event = state["event"]
        query = (
            f"{event.asset_name} {event.error_code} 温度过高 振动异常 "
            "根因 排查 维修 SOP 安全"
        )
        evidence = self.store.similarity_search(query, k=4)
        return {"evidence": evidence, "trace": state["trace"] + ["retrieve_knowledge"]}

    @staticmethod
    def _diagnose(state: MaintenanceState) -> dict:
        event = state["event"]
        evidence_text = " ".join(item.content for item in state.get("evidence", []))
        causes: list[str] = []
        if event.temperature_c >= 75:
            causes.append("散热受阻、负载过高或润滑不足")
        if event.vibration_mm_s >= 7:
            causes.append("轴承磨损、联轴器不对中或安装松动")
        if "风扇" in evidence_text:
            causes.append("冷却风扇或风道异常")
        suspected = "；".join(dict.fromkeys(causes)) or "需现场复核报警码及运行状态"
        actions = [
            "按安全规程停机、断电并执行挂牌上锁（LOTO）",
            "复核温度与振动传感器读数，排除采集异常",
            "检查冷却风道、风扇、轴承、联轴器及紧固状态",
            "处理后空载试运行，并记录温度与振动趋势",
        ]
        return {
            "suspected_cause": suspected,
            "actions": actions,
            "trace": state["trace"] + ["reason_root_cause"],
        }

    def _create_work_order(self, state: MaintenanceState) -> dict:
        event = state["event"]
        priority = "P1" if state["severity"] == "critical" else "P2"
        order = WorkOrder(
            asset_id=event.asset_id,
            title=f"{event.asset_name}异常诊断与检修",
            priority=priority,
            suspected_cause=state["suspected_cause"],
            recommended_actions=state["actions"],
            safety_notice="工单为 AI 草稿，必须由设备工程师复核后执行。",
            evidence=state.get("evidence", []),
        )
        self.settings.work_order_path.parent.mkdir(parents=True, exist_ok=True)
        with self.settings.work_order_path.open("a", encoding="utf-8") as handle:
            handle.write(order.model_dump_json() + "\n")
        return {"work_order": order, "trace": state["trace"] + ["create_work_order"]}

    @staticmethod
    def _finish_normal(state: MaintenanceState) -> dict:
        return {"trace": state["trace"] + ["finish_normal"]}

    def _build_graph(self):
        builder = StateGraph(MaintenanceState)
        builder.add_node("detect", self._detect)
        builder.add_node("retrieve", self._retrieve)
        builder.add_node("diagnose", self._diagnose)
        builder.add_node("create_work_order", self._create_work_order)
        builder.add_node("finish_normal", self._finish_normal)
        builder.add_edge(START, "detect")
        builder.add_conditional_edges(
            "detect", self._route, {"retrieve": "retrieve", "finish_normal": "finish_normal"}
        )
        builder.add_edge("retrieve", "diagnose")
        builder.add_edge("diagnose", "create_work_order")
        builder.add_edge("create_work_order", END)
        builder.add_edge("finish_normal", END)
        return builder.compile()

    def run(self, event: SensorEvent) -> DiagnosisResult:
        result = self.graph.invoke({"event": event})
        return DiagnosisResult(
            anomaly=result["anomaly"],
            severity=result["severity"],
            rationale=result["rationale"],
            work_order=result.get("work_order"),
            workflow_trace=result["trace"],
        )

