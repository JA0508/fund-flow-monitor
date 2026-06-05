from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.local_warehouse import connect_warehouse, initialize_warehouse, rebuild_warehouse_from_csv_directory
from src.snapshot_quality import build_snapshot_file_catalog
from src.warehouse_explorer import (
    build_csv_warehouse_consistency_report,
    build_warehouse_explorer_summary,
    compare_csv_catalog_with_warehouse,
    get_warehouse_captured_time_overview,
    get_warehouse_date_overview,
    get_warehouse_file_records,
    get_warehouse_sector_sample,
    get_warehouse_source_type_summary,
    load_warehouse_if_exists,
    summarize_csv_warehouse_consistency,
    validate_warehouse_explorer_text,
)


def _write_snapshot_csv(directory: Path, date_text: str = "2026-01-15", rows: int = 4) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    sectors = ["半导体", "计算机", "电池", "银行", "医药生物", "证券Ⅱ"]
    data = []
    for idx in range(rows):
        data.append(
            {
                "sector_type": "行业资金流",
                "sector_name": f"{sectors[idx % len(sectors)]}{idx}",
                "main_net_inflow_billion": float((idx + 1) * 3),
                "captured_time": "09:30:00" if idx < rows // 2 else "10:00:00",
                "source": "SAMPLE",
                "trade_date": date_text,
            }
        )
    path = directory / f"sector_flow_{date_text}.csv"
    pd.DataFrame(data).to_csv(path, index=False)
    return path


def _build_temp_warehouse(tmp_path: Path, rows: int = 6):
    csv_dir = tmp_path / "sample_ticks"
    _write_snapshot_csv(csv_dir, rows=rows)
    db_path = tmp_path / "fund_flow.sqlite"
    conn = connect_warehouse(str(db_path))
    initialize_warehouse(conn)
    rebuild = rebuild_warehouse_from_csv_directory(conn, str(csv_dir), "SAMPLE", clear_source=True)
    return conn, csv_dir, rebuild


def test_load_warehouse_if_exists_missing_does_not_create(tmp_path: Path):
    missing = tmp_path / "missing.sqlite"
    conn, status = load_warehouse_if_exists(str(missing))
    assert conn is None
    assert not missing.exists()
    assert status["exists"] is False


def test_load_warehouse_if_exists_existing_can_connect(tmp_path: Path):
    db_path = tmp_path / "fund_flow.sqlite"
    conn = connect_warehouse(str(db_path))
    initialize_warehouse(conn)
    conn.close()
    loaded, status = load_warehouse_if_exists(str(db_path))
    try:
        assert loaded is not None
        assert status["can_connect"] is True
    finally:
        if loaded is not None:
            loaded.close()


def test_source_type_summary_date_and_time_overviews(tmp_path: Path):
    conn, _, _ = _build_temp_warehouse(tmp_path)
    try:
        source_summary = get_warehouse_source_type_summary(conn)
        date_overview = get_warehouse_date_overview(conn)
        time_overview = get_warehouse_captured_time_overview(conn)
    finally:
        conn.close()
    assert source_summary.loc[0, "source_type"] == "SAMPLE"
    assert int(source_summary.loc[0, "row_count"]) == 6
    assert not date_overview.empty
    assert not time_overview.empty
    assert "top_abs_inflow_sector" in time_overview.columns


def test_date_overview_source_filter(tmp_path: Path):
    conn, _, _ = _build_temp_warehouse(tmp_path)
    try:
        sample_dates = get_warehouse_date_overview(conn, source_type="SAMPLE")
        local_dates = get_warehouse_date_overview(conn, source_type="LOCAL")
    finally:
        conn.close()
    assert not sample_dates.empty
    assert local_dates.empty


def test_captured_time_overview_date_filter(tmp_path: Path):
    conn, _, _ = _build_temp_warehouse(tmp_path)
    try:
        overview = get_warehouse_captured_time_overview(conn, source_type="SAMPLE", data_date="2026-01-15")
        missing = get_warehouse_captured_time_overview(conn, source_type="SAMPLE", data_date="2026-01-16")
    finally:
        conn.close()
    assert not overview.empty
    assert missing.empty


def test_sector_sample_respects_top_n_cap(tmp_path: Path):
    conn, _, _ = _build_temp_warehouse(tmp_path, rows=250)
    try:
        sample = get_warehouse_sector_sample(conn, top_n=999)
    finally:
        conn.close()
    assert len(sample) == 200
    assert "main_net_inflow_billion" in sample.columns


def test_sector_sample_filters_and_empty_result(tmp_path: Path):
    conn, _, _ = _build_temp_warehouse(tmp_path)
    try:
        sample = get_warehouse_sector_sample(conn, source_type="SAMPLE", data_date="2026-01-15", captured_time="09:30:00", top_n=10)
        missing = get_warehouse_sector_sample(conn, source_type="LOCAL", top_n=10)
    finally:
        conn.close()
    assert not sample.empty
    assert missing.empty


def test_file_records_and_consistency_match(tmp_path: Path):
    conn, csv_dir, _ = _build_temp_warehouse(tmp_path)
    try:
        files = get_warehouse_file_records(conn, "SAMPLE")
        catalog = build_snapshot_file_catalog(str(csv_dir), pattern="sector_flow_*.csv")
        report = compare_csv_catalog_with_warehouse(catalog, files, "SAMPLE")
    finally:
        conn.close()
    assert not files.empty
    assert report["consistency_label"] == "CSV 与 warehouse 一致"
    assert report["matched_file_count"] == 1


def test_file_records_empty_before_schema(tmp_path: Path):
    db_path = tmp_path / "empty.sqlite"
    conn = connect_warehouse(str(db_path))
    try:
        records = get_warehouse_file_records(conn)
    finally:
        conn.close()
    assert records.empty


def test_compare_csv_catalog_with_warehouse_detects_missing_sides(tmp_path: Path):
    csv_dir = tmp_path / "sample_ticks"
    _write_snapshot_csv(csv_dir)
    catalog = build_snapshot_file_catalog(str(csv_dir), pattern="sector_flow_*.csv")
    csv_only = compare_csv_catalog_with_warehouse(catalog, pd.DataFrame(), "SAMPLE")
    warehouse_only = compare_csv_catalog_with_warehouse(pd.DataFrame(), pd.DataFrame({"source_type": ["SAMPLE"], "file_name": ["sector_flow_2026-01-15.csv"]}), "SAMPLE")
    assert csv_only["consistency_label"] == "仅 CSV 可用"
    assert warehouse_only["consistency_label"] == "仅 warehouse 可用"


def test_compare_csv_catalog_with_warehouse_detects_count_mismatch(tmp_path: Path):
    csv_dir = tmp_path / "sample_ticks"
    _write_snapshot_csv(csv_dir, rows=4)
    catalog = build_snapshot_file_catalog(str(csv_dir), pattern="sector_flow_*.csv")
    wh = pd.DataFrame(
        {
            "source_type": ["SAMPLE"],
            "file_name": ["sector_flow_2026-01-15.csv"],
            "row_count": [999],
            "captured_time_count": [1],
        }
    )
    report = compare_csv_catalog_with_warehouse(catalog, wh, "SAMPLE")
    assert report["consistency_label"] == "warehouse 需要重建"
    assert report["row_count_mismatch"]


def test_consistency_report_conn_none_is_readable():
    report = build_csv_warehouse_consistency_report(None)
    assert report["overall_label"] == "warehouse 未创建"
    assert report["warehouse_exists"] is False


def test_consistency_report_with_temp_csv_and_warehouse(tmp_path: Path):
    conn, csv_dir, _ = _build_temp_warehouse(tmp_path)
    empty_local = tmp_path / "empty_local"
    empty_local.mkdir()
    try:
        report = build_csv_warehouse_consistency_report(conn, local_csv_dir=str(empty_local), sample_csv_dir=str(csv_dir))
    finally:
        conn.close()
    assert report["sample_consistency"]["consistency_label"] == "CSV 与 warehouse 一致"
    assert report["overall_label"] in {"SAMPLE 一致，LOCAL 未导入", "CSV 与 warehouse 基本一致"}


def test_explorer_summary_handles_none_and_temp_warehouse(tmp_path: Path):
    none_summary = build_warehouse_explorer_summary(None)
    assert none_summary["explorer_available"] is False
    conn, _, _ = _build_temp_warehouse(tmp_path)
    try:
        summary = build_warehouse_explorer_summary(conn)
    finally:
        conn.close()
    assert summary["explorer_available"] is True
    assert summary["row_count"] > 0


def test_summarize_and_validate_explorer_text():
    text = summarize_csv_warehouse_consistency(
        {
            "warehouse_exists": True,
            "overall_label": "SAMPLE 一致，LOCAL 未导入",
            "overall_reason": "SAMPLE CSV 与 warehouse 基本一致；LOCAL CSV 尚未导入。",
        }
    )
    assert "CSV" in text
    assert validate_warehouse_explorer_text(text) == []
    assert validate_warehouse_explorer_text("建议买") == ["建议买"]


def test_normal_explorer_summary_text_has_no_forbidden_words():
    text = summarize_csv_warehouse_consistency(
        {
            "warehouse_exists": True,
            "overall_label": "CSV 与 warehouse 基本一致",
            "overall_reason": "SAMPLE CSV 与 warehouse 基本一致。",
        }
    )
    assert validate_warehouse_explorer_text(text) == []
