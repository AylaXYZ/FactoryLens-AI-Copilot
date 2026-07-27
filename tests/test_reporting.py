from factorylens.reporting import build_production_report
from factorylens.schemas import ProductionRecord


def test_report_flags_low_attainment_and_downtime():
    report = build_production_report(
        [
            ProductionRecord(
                date="2026-07-27",
                line="包装二线",
                planned_qty=1000,
                actual_qty=850,
                downtime_minutes=80,
                alarms=7,
            )
        ]
    )
    assert report.plan_attainment == 0.85
    assert len(report.risks) == 3
    assert "计划达成率" in report.summary

