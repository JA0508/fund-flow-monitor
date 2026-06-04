from __future__ import annotations

import pandas as pd

from src.snapshot_quality import (
    audit_snapshot_csv_file,
    audit_snapshot_dataframe,
    build_snapshot_file_catalog,
    build_snapshot_quality_report,
    detect_duplicate_captured_times,
    get_snapshot_required_columns,
    normalize_snapshot_columns,
    summarize_snapshot_quality,
    validate_snapshot_quality_text,
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "captured_time": ["10:00:00", "10:00:00", "10:05:00"],
            "sector_type": ["行业资金流", "行业资金流", "行业资金流"],
            "sector_name": ["半导体", "半导体", "银行"],
            "main_net_inflow_billion": [12.5, 12.5, -5.2],
        }
    )


def test_get_snapshot_required_columns_returns_non_empty_list():
    assert get_snapshot_required_columns()
    assert "captured_time" in get_snapshot_required_columns()


def test_normalize_snapshot_columns_handles_aliases():
    raw = pd.DataFrame({"板块名称": ["半导体"], "主力净流入-净额": [100_000_000], "采集时间": ["10:00:00"]})
    normalized = normalize_snapshot_columns(raw)
    assert normalized["sector_name"].iloc[0] == "半导体"
    assert normalized["main_net_inflow_billion"].iloc[0] == 1.0
    assert normalized["captured_time"].iloc[0] == "10:00:00"


def test_audit_snapshot_dataframe_handles_empty_df():
    audit = audit_snapshot_dataframe(pd.DataFrame())
    assert audit["row_count"] == 0
    assert audit["quality_label"] == "无可用数据"


def test_audit_snapshot_dataframe_detects_missing_required_columns():
    audit = audit_snapshot_dataframe(pd.DataFrame({"captured_time": ["10:00:00"]}))
    assert "sector_name" in audit["missing_required_columns"]
    assert audit["errors"]


def test_audit_snapshot_dataframe_detects_invalid_numeric():
    df = pd.DataFrame({"captured_time": ["10:00:00"], "sector_name": ["半导体"], "main_net_inflow_billion": ["bad"]})
    audit = audit_snapshot_dataframe(df)
    assert audit["invalid_numeric_count"] == 1
    assert audit["quality_label"] in {"存在轻微警告", "存在明显问题"}


def test_audit_snapshot_dataframe_detects_duplicate_sector_time():
    audit = audit_snapshot_dataframe(_sample_df())
    assert audit["duplicate_row_count"] == 1
    assert audit["duplicate_captured_time_count"] == 1


def test_audit_snapshot_csv_file_missing_file_does_not_crash(tmp_path):
    audit = audit_snapshot_csv_file(str(tmp_path / "missing.csv"))
    assert audit["errors"]
    assert audit["quality_label"] == "无可用数据"


def test_build_snapshot_file_catalog_missing_directory_returns_empty(tmp_path):
    catalog = build_snapshot_file_catalog(str(tmp_path / "not-exist"))
    assert catalog.empty


def test_build_snapshot_file_catalog_scans_temp_csv(tmp_path):
    path = tmp_path / "sector_flow_2026-06-01.csv"
    _sample_df().to_csv(path, index=False)
    catalog = build_snapshot_file_catalog(str(tmp_path))
    assert len(catalog) == 1
    assert catalog["row_count"].iloc[0] == 3
    assert catalog["captured_time_count"].iloc[0] == 2


def test_build_snapshot_quality_report_handles_local_and_sample(tmp_path):
    local = tmp_path / "local"
    sample = tmp_path / "sample"
    local.mkdir()
    sample.mkdir()
    _sample_df().to_csv(local / "sector_flow_2026-06-01.csv", index=False)
    _sample_df().to_csv(sample / "sector_flow_2026-01-15.csv", index=False)
    report = build_snapshot_quality_report(str(local), str(sample))
    assert report["local_file_count"] == 1
    assert report["sample_file_count"] == 1
    assert report["report_label"] in {"本地缓存可用", "存在坏 CSV"}


def test_detect_duplicate_captured_times_finds_duplicates():
    duplicates = detect_duplicate_captured_times(_sample_df())
    assert not duplicates.empty
    assert duplicates["duplicate_count"].iloc[0] == 2


def test_summarize_snapshot_quality_outputs_chinese_text():
    report = {
        "local_file_count": 1,
        "sample_file_count": 1,
        "local_latest_date": "2026-06-01",
        "sample_latest_date": "2026-01-16",
        "local_warning_count": 0,
        "local_error_count": 0,
        "sample_warning_count": 0,
        "sample_error_count": 0,
    }
    text = summarize_snapshot_quality(report)
    assert "本地真实缓存" in text
    assert validate_snapshot_quality_text(text) == []


def test_validate_snapshot_quality_text_detects_forbidden_words():
    hits = validate_snapshot_quality_text("建议买入并加仓")
    assert "买入" in hits
    assert "加仓" in hits
