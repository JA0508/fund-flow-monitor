from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.theme_taxonomy import load_theme_taxonomy
from src.theme_taxonomy_audit import (
    build_cross_theme_overlap_audit,
    build_source_universe_coverage_audit,
    build_taxonomy_audit_report,
    build_theme_calibration_report,
    classify_overlap_state,
    validate_taxonomy_audit_text,
)


def _snapshot_row(name: str) -> dict:
    return {
        "trade_date": "2026-01-16",
        "captured_at": "2026-01-16 14:50:00",
        "captured_time": "14:50:00",
        "sector_type": "行业资金流",
        "sector_name": name,
        "main_net_inflow_billion": 1.0,
        "source": "REAL",
        "data_mode": "REAL",
    }


def test_overlap_state_thresholds() -> None:
    assert classify_overlap_state(0) == "none"
    assert classify_overlap_state(0.15) == "low_overlap"
    assert classify_overlap_state(0.3) == "moderate_overlap"
    assert classify_overlap_state(0.7) == "high_overlap"


def test_cross_theme_overlap_detects_reused_bank() -> None:
    taxonomy = load_theme_taxonomy()
    overlap = build_cross_theme_overlap_audit(taxonomy)
    assert not overlap.empty
    shared_rows = overlap[overlap["shared_member_count"].gt(0)]
    assert "银行" in {member for values in shared_rows["shared_members"] for member in values}


def test_sample_source_universe_coverage_is_factual() -> None:
    coverage = build_source_universe_coverage_audit(load_theme_taxonomy(), source_mode="SAMPLE")
    assert coverage["source_mode"] == "SAMPLE"
    assert coverage["unique_source_row_count"] == 20
    assert coverage["mapped_source_row_count"] > 0
    assert "mapped unique normalized source rows" in coverage["denominator_note"]
    assert coverage["ambiguous_source_row_count"] == 1
    assert coverage["ambiguous_source_rows"][0]["sector_name"] == "银行"


def test_real_temporary_source_universe_coverage(tmp_path: Path) -> None:
    pd.DataFrame([_snapshot_row("半导体"), _snapshot_row("未知板块")]).to_csv(
        tmp_path / "sector_flow_2026-01-16.csv",
        index=False,
    )
    coverage = build_source_universe_coverage_audit(load_theme_taxonomy(), source_mode="REAL", data_dir=str(tmp_path))
    assert coverage["source_mode"] == "REAL"
    assert coverage["unique_source_row_count"] == 2
    assert coverage["mapped_source_row_count"] == 1
    assert coverage["unmapped_source_row_count"] == 1


def test_real_missing_cache_returns_empty_state(tmp_path: Path) -> None:
    coverage = build_source_universe_coverage_audit(load_theme_taxonomy(), source_mode="REAL", data_dir=str(tmp_path))
    assert coverage["source_available"] is False
    assert coverage["mapping_coverage_rate"] == 0.0


def test_calibration_report_contains_role_and_overlap_context() -> None:
    report = build_theme_calibration_report(load_theme_taxonomy(), source_mode="SAMPLE")
    assert not report.empty
    row = report[report["theme_name"].eq("半导体/芯片链")].iloc[0]
    assert row["core_count"] >= 1
    assert row["strict_representative_count"] >= 1
    assert isinstance(row["member_provenance_counts"], dict)
    assert "manual_domain_mapping" in row["member_provenance_counts"]


def test_taxonomy_audit_report_summary_fields() -> None:
    report = build_taxonomy_audit_report(load_theme_taxonomy(), source_mode="SAMPLE")
    assert report["theme_count"] == 8
    assert report["member_assignment_count"] == 80
    assert report["unique_canonical_member_count"] == 79
    assert report["reused_members"] == {"银行": 2}
    assert report["validation"]["error_count"] == 0


def test_taxonomy_audit_text_validator() -> None:
    assert "未来会涨" in validate_taxonomy_audit_text("未来会涨")
    assert validate_taxonomy_audit_text("该审计只解释主题语义映射和 source-universe 覆盖。") == []
