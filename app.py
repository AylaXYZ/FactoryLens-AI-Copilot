from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from factorylens.config import get_settings
from factorylens.ingestion import SUPPORTED_EXTENSIONS, load_and_chunk
from factorylens.llm import build_context
from factorylens.rag import RAGService
from factorylens.reporting import build_production_report
from factorylens.schemas import ProductionRecord, SensorEvent
from factorylens.vector_store import create_store
from factorylens.workflow import MaintenanceWorkflow

st.set_page_config(
    page_title="FactoryLens Semantic RAG Agent",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { --ink:#10231d; --muted:#60756d; --mint:#b9f5d1; --lime:#d9ff68; --paper:#f5f7f2; }
    .stApp { background: linear-gradient(135deg,#f7faf6 0%,#eef5f0 52%,#f8f4e9 100%); color:var(--ink); }
    [data-testid="stSidebar"] { background:#10231d; }
    [data-testid="stSidebar"] * { color:#eef7f2 !important; }
    .hero { padding:2.1rem 2.3rem; border-radius:24px; background:#10231d; color:white;
            box-shadow:0 18px 50px rgba(16,35,29,.14); margin-bottom:1.2rem; position:relative; overflow:hidden; }
    .hero:after { content:""; position:absolute; width:260px; height:260px; right:-80px; top:-130px;
                  border-radius:50%; background:var(--lime); opacity:.75; }
    .eyebrow { color:#b9f5d1; letter-spacing:.14em; font-weight:700; font-size:.78rem; }
    .hero h1 { font-size:2.8rem; line-height:1.04; margin:.45rem 0 .8rem; color:white; }
    .hero p { color:#c9d8d1; max-width:700px; font-size:1.03rem; }
    .metric { padding:1rem 1.15rem; border:1px solid rgba(16,35,29,.10); border-radius:18px;
              background:rgba(255,255,255,.72); min-height:108px; }
    .metric b { font-size:1.75rem; display:block; margin-top:.25rem; }
    .metric span { color:var(--muted); font-size:.85rem; }
    .step { padding:.9rem 1rem; border-radius:14px; background:#fff; border-left:4px solid #77c994; margin:.4rem 0; }
    .source { padding:.8rem 1rem; border-radius:12px; background:#f8fbf8; border:1px solid #dce9e1; margin:.5rem 0; }
    div[data-testid="stButton"] button { border-radius:12px; font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def services():
    settings = get_settings()
    store = create_store(settings)
    rag = RAGService(settings=settings, store=store)
    workflow = MaintenanceWorkflow(settings=settings, store=store)
    return settings, store, rag, workflow


settings, store, rag, workflow = services()


def ingest_demo_if_needed() -> int:
    if store.count:
        return 0
    paths = list((ROOT / "knowledge_base").glob("*"))
    chunks = load_and_chunk(path for path in paths if path.suffix.lower() in SUPPORTED_EXTENSIONS)
    return store.add_documents(chunks)


ingest_demo_if_needed()

with st.sidebar:
    st.markdown("## ◈ FactoryLens")
    st.caption("语义 RAG 与设备运维智能体")
    page = st.radio(
        "工作台",
        ["知识问答", "故障诊断 Agent", "生产日报", "知识库管理", "架构与接口"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("运行状态")
    st.write(f"**{store.count}** 个知识切片")
    st.write(f"模型：`{rag.generator.provider_name}`")
    st.write(f"向量：`{store.embedding_provider_name}`")
    st.success("本地演示模式可用")
    st.caption("AI 结论仅供辅助，设备处置需人工复核。")

st.markdown(
    """
    <section class="hero">
      <div class="eyebrow">SEMANTIC RAG · LANGGRAPH · FASTAPI</div>
      <h1>让设备知识可检索，<br/>让异常处理可闭环。</h1>
      <p>从企业文档接入、证据检索，到根因分析与维修工单生成。一套可在本地运行、
      可通过 API 集成 MES / SCADA / ERP 的制造业 AI Copilot。</p>
    </section>
    """,
    unsafe_allow_html=True,
)

metric_cols = st.columns(4)
for col, label, value in zip(
    metric_cols,
    ["知识切片", "支持格式", "智能体节点", "外部 API"],
    [str(store.count), "PDF / Word / Excel", "4-step", "FastAPI"],
    strict=True,
):
    col.markdown(
        f'<div class="metric"><span>{label}</span><b>{value}</b></div>', unsafe_allow_html=True
    )

st.write("")

if page == "知识问答":
    st.subheader("工艺与设备知识问答")
    st.caption("回答严格引用知识库；资料不足时拒绝编造。")
    with st.form("qa-form"):
        question = st.text_input(
            "输入问题",
            value="伺服电机出现 E-OVHT-07 且温度持续升高时，应如何排查？",
        )
        submitted = st.form_submit_button("检索并生成答案", type="primary")
    if submitted:
        with st.spinner("正在检索知识并组织证据…"):
            result = rag.ask(question)
        st.markdown("#### 回答")
        st.markdown(result.answer)
        st.markdown("#### 引用证据")
        for index, source in enumerate(result.sources, start=1):
            location = f"第 {source.page} 页" if source.page else source.sheet or "文档"
            st.markdown(
                f'<div class="source"><b>[{index}] {source.source}</b> · {location} · '
                f"相似度 {source.score:.2f}<br><span>{source.content[:300]}</span></div>",
                unsafe_allow_html=True,
            )
        with st.expander("查看 RAG 检索与 Prompt 上下文"):
            st.caption(
                "查询先经过向量化，再按相似度召回 Top-K 切片；以下内容会作为上下文交给生成模型。"
            )
            rows = [
                {
                    "排名": index,
                    "来源": source.source,
                    "位置": f"第 {source.page} 页" if source.page else source.sheet or "文档",
                    "相似度": source.score,
                    "切片 ID": source.chunk_id,
                    "内容预览": source.content[:160],
                }
                for index, source in enumerate(result.sources, start=1)
            ]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.code(build_context(result.sources), language="text")

elif page == "故障诊断 Agent":
    st.subheader("设备异常 → 根因 → 工单")
    st.caption("规则负责安全边界，RAG 提供知识证据，LangGraph 编排闭环。")
    c1, c2, c3 = st.columns(3)
    asset_id = c1.text_input("设备编号", "PKG-L2-M07")
    temperature = c2.number_input("温度（°C）", 0.0, 150.0, 86.0, 0.5)
    vibration = c3.number_input("振动（mm/s）", 0.0, 30.0, 8.1, 0.1)
    error_code = st.text_input("报警码", "E-OVHT-07")
    if st.button("启动诊断工作流", type="primary"):
        result = workflow.run(
            SensorEvent(
                asset_id=asset_id,
                temperature_c=temperature,
                vibration_mm_s=vibration,
                error_code=error_code,
            )
        )
        color = "red" if result.severity == "critical" else "orange"
        st.markdown(f"#### 判定：:{color}[{result.severity.upper()}]")
        st.write(result.rationale)
        st.markdown("#### 工作流轨迹")
        labels = {
            "detect_anomaly": "① 感知异常",
            "retrieve_knowledge": "② 检索知识",
            "reason_root_cause": "③ 根因推理",
            "create_work_order": "④ 生成工单",
            "finish_normal": "② 正常结束",
        }
        for step in result.workflow_trace:
            st.markdown(f'<div class="step">{labels.get(step, step)}</div>', unsafe_allow_html=True)
        if result.work_order:
            order = result.work_order
            st.markdown(f"#### {order.work_order_id} · {order.priority}")
            st.write(f"**疑似根因：** {order.suspected_cause}")
            for action in order.recommended_actions:
                st.write(f"- {action}")
            st.warning(order.safety_notice)
            st.download_button(
                "下载工单 JSON",
                data=order.model_dump_json(indent=2),
                file_name=f"{order.work_order_id}.json",
                mime="application/json",
            )

elif page == "生产日报":
    st.subheader("生产日报自动生成")
    st.caption("模拟 MES 数据接入：上传 CSV，或使用内置样例。")
    uploaded = st.file_uploader("上传生产数据", type=["csv"])
    sample_path = ROOT / "data" / "sample_production.csv"
    frame = pd.read_csv(uploaded if uploaded else sample_path)
    st.dataframe(frame, width="stretch", hide_index=True)
    if st.button("生成日报", type="primary"):
        records = [ProductionRecord(**row) for row in frame.to_dict(orient="records")]
        report = build_production_report(records)
        st.markdown(f"#### {report.title}")
        st.write(report.summary)
        a, b, c = st.columns(3)
        a.metric("计划达成率", f"{report.plan_attainment:.1%}")
        b.metric("停机时间", f"{report.total_downtime_minutes} 分钟")
        c.metric("报警次数", report.alarm_count)
        st.write("**风险**")
        for item in report.risks:
            st.write(f"- {item}")
        st.write("**建议动作**")
        for item in report.actions:
            st.write(f"- {item}")

elif page == "知识库管理":
    st.subheader("文档接入管道")
    st.caption("自动解析 → 分块 → 向量化 → 去重入库。")
    uploads = st.file_uploader(
        "上传企业文档",
        type=["pdf", "docx", "xlsx", "xls", "csv", "txt", "md"],
        accept_multiple_files=True,
    )
    if uploads and st.button("开始入库", type="primary"):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for uploaded_file in uploads:
                safe_name = Path(uploaded_file.name).name
                path = Path(tmp) / safe_name
                path.write_bytes(uploaded_file.getbuffer())
                paths.append(path)
            chunks = load_and_chunk(paths)
            added = store.add_documents(chunks)
        st.success(f"解析 {len(uploads)} 个文件、生成 {len(chunks)} 个切片、新增 {added} 个。")
    st.info("默认样例知识库为完全虚构数据，可安全公开到 GitHub。")

else:
    st.subheader("架构与集成")
    st.code(
        """
PDF / Word / Excel / CSV
          │
    文档解析与分块
          │
    向量检索 + 引用
          │
 ┌────────┴─────────┐
知识问答        LangGraph 运维 Agent
                  │
       检测 → 检索 → 诊断 → 工单
                  │
          FastAPI / MES / ERP
        """,
        language="text",
    )
    st.write("启动 API 后访问：`http://127.0.0.1:8000/docs`")
    st.code(
        json.dumps(
            {
                "asset_id": "PKG-L2-M07",
                "temperature_c": 86.0,
                "vibration_mm_s": 8.1,
                "error_code": "E-OVHT-07",
            },
            ensure_ascii=False,
            indent=2,
        ),
        language="json",
    )
