from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data_contracts import (
    SAMPLE_REQUIRED_COLUMNS,
    SNAPSHOT_REQUIRED_COLUMNS,
    summarize_data_contract_report,
    validate_data_contract_text,
    validate_sample_snapshot_dataframe,
    validate_snapshot_csv_file,
    validate_snapshot_dataframe,
    validate_snapshot_directory,
)


def _snapshot_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trade_date": "2026-01-15",
                "captured_at": "2026-01-15 09:35:00",
                "captured_time": "09:35:00",
                "sector_type": "行业资金流",
                "sector_code": "801080",
                "sector_name": "半导体",
                "change_pct": 1.2,
                "main_net_inflow_yuan": 120000000,
                "main_net_inflow_billion": 1.2,
                "source": "SAMPLE",
                "data_mode": "SAMPLE",
            },
            {
                "trade_date": "2026-01-15",
                "captured_at": "2026-01-15 09:35:00",
                "captured_time": "09:35:00",
                "sector_type": "概念资金流",
                "sector_code": "BK001",
                "sector_name": "AI应用",
                "change_pct": -0.5,
                "main_net_inflow_yuan": -30000000,
                "main_net_inflow_billion": -0.3,
                "source": "SAMPLE",
                "data_mode": "SAMPLE",
            },
        ]
    )


def test_required_column_constants_are_non_empty():
    assert "sector_name" in SNAPSHOT_REQUIRED_COLUMNS
    assert "data_mode" in SAMPLE_REQUIRED_COLUMNS


def test_validate_snapshot_dataframe_empty_fails_readably():
    report = validate_snapshot_dataframe(pd.DataFrame())
    assert report["contract_ok"] is False
    assert report["error_count"] > 0


def test_validate_snapshot_dataframe_basic_passes():
    report = validate_snapshot_dataframe(_snapshot_df())
    assert report["contract_ok"] is True
    assert report["industry_row_count"] == 1
    assert report["concept_row_count"] == 1


def test_validate_snapshot_dataframe_missing_required_column():
    df = _snapshot_df().drop(columns=["sector_name"])
    report = validate_snapshot_dataframe(df)
    assert report["contract_ok"] is False
    assert "sector_name" in report["missing_required_columns"]


def test_validate_snapshot_dataframe_invalid_numeric_column():
    df = _snapshot_df()
    df["main_net_inflow_billion"] = df["main_net_inflow_billion"].astype("object")
    df.loc[0, "main_net_inflow_billion"] = "not-a-number"
    report = validate_snapshot_dataframe(df)
    assert report["contract_ok"] is False
    assert "main_net_inflow_billion" in report["invalid_numeric_columns"]


def test_validate_sample_snapshot_dataframe_requires_sample_markers():
    df = _snapshot_df()
    df.loc[0, "source"] = "LOCAL"
    report = validate_sample_snapshot_dataframe(df)
    assert report["contract_ok"] is False
    assert report["sample_marker_ok"] is False


def test_validate_sample_snapshot_dataframe_passes():
    report = validate_sample_snapshot_dataframe(_snapshot_df())
    assert report["contract_ok"] is True
    assert report["sample_marker_ok"] is True


def test_validate_snapshot_csv_file(tmp_path: Path):
    path = tmp_path / "sector_flow_2026-01-15.csv"
    _snapshot_df().to_csv(path, index=False)
    report = validate_snapshot_csv_file(path, sample=True)
    assert report["contract_ok"] is True
    assert report["file_name"] == path.name


def test_validate_snapshot_directory_missing_does_not_crash(tmp_path: Path):
    report = validate_snapshot_directory(tmp_path / "missing", sample=True)
    assert report["contract_ok"] is False
    assert report["error_count"] == 0
    assert report["warning_count"] == 1


def test_validate_snapshot_directory_sample_csv(tmp_path: Path):
    sample_dir = tmp_path / "sample_data/ticks"
    sample_dir.mkdir(parents=True)
    _snapshot_df().to_csv(sample_dir / "sector_flow_2026-01-15.csv", index=False)
    report = validate_snapshot_directory(sample_dir, sample=True)
    assert report["contract_ok"] is True
    assert report["file_count"] == 1
    assert report["row_count"] == 2


def test_summarize_data_contract_report_is_plain_language():
    text = summarize_data_contract_report({"contract_label": "目录数据契约通过", "file_count": 2, "row_count": 200})
    assert "CSV" in text
    assert validate_data_contract_text(text) == []


def test_validate_data_contract_text_detects_forbidden_phrase():
    assert "未来会涨" in validate_data_contract_text("这个主题未来会涨")
