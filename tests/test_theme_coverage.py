from __future__ import annotations

import pandas as pd

from src.theme_coverage import (
    build_overlap_warning_report,
    build_theme_coverage_report,
    build_theme_usage_report,
    summarize_coverage_report,
)
from src.theme_taxonomy import load_theme_taxonomy


FORBIDDEN = ["买入", "卖出", "加仓", "减仓", "抄底", "逃顶", "推荐买", "建议买", "建仓", "清仓"]


def _row(name: str, value: float) -> dict:
    return {
        "sector_name": name,
        "main_net_inflow_billion": value,
        "theme_name": name,
        "theme_status": "强流入" if value > 0 else "强流出",
        "match_strategy": "primary_exact",
        "source_sector_count": 1,
        "used_sectors": name,
    }


def test_build_theme_coverage_report_counts_uncovered_and_ratio() -> None:
    taxonomy = load_theme_taxonomy()
    latest = pd.DataFrame([_row("半导体", 10), _row("未知高流板块", 30), _row("计算机", 5)])
    report = build_theme_coverage_report(latest, taxonomy)
    assert report["total_sectors"] == 3
    assert report["covered_sector_count"] == 2
    assert round(report["coverage_ratio"], 2) == 0.67
    assert "未知高流板块" in report["top_uncovered_sectors_df"]["sector_name"].tolist()
    assert "未知高流板块" in report["high_flow_uncovered_df"]["sector_name"].tolist()


def test_build_theme_coverage_report_detects_duplicated_sectors() -> None:
    taxonomy = load_theme_taxonomy()
    report = build_theme_coverage_report(pd.DataFrame([_row("银行", 1)]), taxonomy)
    duplicated = report["duplicated_sector_df"]
    assert not duplicated.empty
    assert "银行" in duplicated["sector_name"].tolist()


def test_build_theme_usage_report_outputs_usage_fields() -> None:
    taxonomy = load_theme_taxonomy()
    theme_snapshot = pd.DataFrame(
        [
            {
                "theme_name": "半导体/芯片链",
                "main_net_inflow_billion": 10,
                "theme_status": "强流入",
                "match_strategy": "primary_exact",
                "source_sector_count": 1,
                "used_sectors": "半导体",
            }
        ]
    )
    usage = build_theme_usage_report(theme_snapshot, taxonomy)
    row = usage[usage["theme_name"].eq("半导体/芯片链")].iloc[0]
    assert row["has_primary_match"] is True or bool(row["has_primary_match"]) is True
    assert {"taxonomy_primary_count", "taxonomy_related_count", "coverage_note"}.issubset(usage.columns)


def test_overlap_warning_report_and_summary_are_safe() -> None:
    taxonomy = load_theme_taxonomy()
    overlap = build_overlap_warning_report(taxonomy)
    assert not overlap.empty
    summary = summarize_coverage_report(build_theme_coverage_report(pd.DataFrame([_row("半导体", 1)]), taxonomy))
    text = " ".join(overlap["warning_reason"].tolist() + [summary])
    for word in FORBIDDEN:
        assert word not in text
