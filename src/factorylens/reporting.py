from __future__ import annotations

from factorylens.schemas import ProductionRecord, ProductionReport


def build_production_report(records: list[ProductionRecord]) -> ProductionReport:
    if not records:
        raise ValueError("At least one production record is required")
    planned = sum(item.planned_qty for item in records)
    actual = sum(item.actual_qty for item in records)
    downtime = sum(item.downtime_minutes for item in records)
    alarms = sum(item.alarms for item in records)
    attainment = actual / planned if planned else 0.0

    risks = []
    actions = []
    if attainment < 0.95:
        risks.append(f"计划达成率仅 {attainment:.1%}，存在交付风险")
        actions.append("复核瓶颈工序和缺料清单，调整次日排程")
    if downtime >= 60:
        risks.append(f"累计停机 {downtime} 分钟，超过日常关注阈值")
        actions.append("按停机原因 Pareto 排序，优先处理前三项")
    if alarms >= 5:
        risks.append(f"设备报警 {alarms} 次，建议检查重复报警")
        actions.append("将高频报警关联至设备工单并追踪闭环")
    if not risks:
        risks.append("未发现明显异常")
        actions.append("维持当前节奏并持续监控关键指标")

    return ProductionReport(
        title=f"{records[0].date} 生产日报",
        summary=(
            f"共 {len(records)} 条产线记录，完成 {actual}/{planned} 件，"
            f"计划达成率 {attainment:.1%}；停机 {downtime} 分钟，报警 {alarms} 次。"
        ),
        plan_attainment=round(attainment, 4),
        total_downtime_minutes=downtime,
        alarm_count=alarms,
        risks=risks,
        actions=actions,
    )

