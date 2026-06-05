from __future__ import annotations

import sqlite3

import pandas as pd

from src.local_warehouse import (
    audit_warehouse,
    connect_warehouse,
    get_default_warehouse_path,
    initialize_warehouse,
    insert_snapshot_rows,
    normalize_snapshot_df_for_warehouse,
    query_available_dates,
    query_snapshot_rows,
    query_warehouse_summary,
    rebuild_warehouse_from_csv_directory,
    summarize_warehouse_status,
    validate_warehouse_text,
)


def _snapshot_df(captured_time: str = "10:00:00") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trade_date": ["2026-01-15", "2026-01-15"],
            "captured_at": ["2026-01-15 10:00:00", "2026-01-15 10:00:00"],
            "captured_time": [captured_time, captured_time],
            "sector_type": ["行业资金流", "行业资金流"],
            "sector_name": ["半导体", "银行"],
            "main_net_inflow_billion": [12.0, -6.0],
            "change_pct": [1.2, -0.5],
            "source": ["TEST", "TEST"],
        }
    )


def _connect_tmp(tmp_path):
    conn = connect_warehouse(str(tmp_path / "warehouse.sqlite"))
    initialize_warehouse(conn)
    return conn


def test_get_default_warehouse_path_returns_expected_path():
    assert get_default_warehouse_path() == "data/warehouse/fund_flow.sqlite"


def test_initialize_warehouse_creates_tables(tmp_path):
    conn = _connect_tmp(tmp_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    finally:
        conn.close()
    assert {"snapshot_files", "snapshot_rows", "warehouse_meta"}.issubset(tables)


def test_normalize_snapshot_df_for_warehouse_handles_basic_df():
    rows = normalize_snapshot_df_for_warehouse(_snapshot_df(), "SAMPLE", imported_file="sample.csv")
    assert set(["source_type", "sector_name", "captured_time"]).issubset(rows.columns)
    assert rows["source_type"].iloc[0] == "SAMPLE"
    assert rows["main_net_inflow_billion"].iloc[0] == 12.0


def test_normalize_snapshot_df_for_warehouse_maps_name_to_sector_name():
    raw = pd.DataFrame({"name": ["计算机"], "captured_time": ["09:30:00"], "main_net_inflow_billion": [3.0]})
    rows = normalize_snapshot_df_for_warehouse(raw, "LOCAL")
    assert rows["sector_name"].iloc[0] == "计算机"


def test_insert_snapshot_rows_writes_data(tmp_path):
    conn = _connect_tmp(tmp_path)
    try:
        rows = normalize_snapshot_df_for_warehouse(_snapshot_df(), "SAMPLE", imported_file="sample.csv")
        result = insert_snapshot_rows(conn, rows)
        assert result["inserted_rows"] == 2
        assert query_warehouse_summary(conn)["snapshot_row_count"] == 2
    finally:
        conn.close()


def test_insert_snapshot_rows_skips_duplicates(tmp_path):
    conn = _connect_tmp(tmp_path)
    try:
        rows = normalize_snapshot_df_for_warehouse(_snapshot_df(), "SAMPLE", imported_file="sample.csv")
        insert_snapshot_rows(conn, rows)
        second = insert_snapshot_rows(conn, rows)
        assert second["inserted_rows"] == 0
        assert second["skipped_duplicate_rows"] == 2
    finally:
        conn.close()


def test_insert_snapshot_rows_replace_existing_replaces_same_imported_file(tmp_path):
    conn = _connect_tmp(tmp_path)
    try:
        rows = normalize_snapshot_df_for_warehouse(_snapshot_df(), "SAMPLE", imported_file="sample.csv")
        insert_snapshot_rows(conn, rows)
        replacement = _snapshot_df()
        replacement["main_net_inflow_billion"] = [20.0, -2.0]
        replacement_rows = normalize_snapshot_df_for_warehouse(replacement, "SAMPLE", imported_file="sample.csv")
        result = insert_snapshot_rows(conn, replacement_rows, replace_existing=True)
        latest = query_snapshot_rows(conn)
        assert result["inserted_rows"] == 2
        assert len(latest) == 2
        assert float(latest["main_net_inflow_billion"].max()) == 20.0
    finally:
        conn.close()


def test_rebuild_warehouse_from_csv_directory_missing_dir_does_not_crash(tmp_path):
    conn = _connect_tmp(tmp_path)
    try:
        result = rebuild_warehouse_from_csv_directory(conn, str(tmp_path / "missing"), "SAMPLE")
        assert result["file_count"] == 0
        assert result["rebuild_label"] == "无可导入文件"
    finally:
        conn.close()


def test_rebuild_warehouse_from_csv_directory_imports_tmp_csv(tmp_path):
    csv_dir = tmp_path / "ticks"
    csv_dir.mkdir()
    _snapshot_df().to_csv(csv_dir / "sector_flow_2026-01-15.csv", index=False)
    conn = _connect_tmp(tmp_path)
    try:
        result = rebuild_warehouse_from_csv_directory(conn, str(csv_dir), "SAMPLE", clear_source=True)
        assert result["imported_file_count"] == 1
        assert result["inserted_rows"] == 2
        assert query_warehouse_summary(conn)["sample_row_count"] == 2
    finally:
        conn.close()


def test_query_warehouse_summary_returns_counts(tmp_path):
    conn = _connect_tmp(tmp_path)
    try:
        rows = normalize_snapshot_df_for_warehouse(_snapshot_df(), "LOCAL", imported_file="local.csv")
        insert_snapshot_rows(conn, rows)
        summary = query_warehouse_summary(conn)
        assert summary["snapshot_row_count"] == 2
        assert summary["local_row_count"] == 2
    finally:
        conn.close()


def test_query_available_dates_returns_date_table(tmp_path):
    conn = _connect_tmp(tmp_path)
    try:
        rows = normalize_snapshot_df_for_warehouse(_snapshot_df(), "SAMPLE", data_date="2026-01-15", imported_file="sample.csv")
        insert_snapshot_rows(conn, rows)
        dates = query_available_dates(conn, "SAMPLE")
        assert len(dates) == 1
        assert dates["data_date"].iloc[0] == "2026-01-15"
    finally:
        conn.close()


def test_query_snapshot_rows_latest_only_returns_latest_time(tmp_path):
    conn = _connect_tmp(tmp_path)
    try:
        first = normalize_snapshot_df_for_warehouse(_snapshot_df("09:30:00"), "SAMPLE", imported_file="a.csv")
        second = normalize_snapshot_df_for_warehouse(_snapshot_df("10:00:00"), "SAMPLE", imported_file="b.csv")
        insert_snapshot_rows(conn, pd.concat([first, second], ignore_index=True))
        latest = query_snapshot_rows(conn, source_type="SAMPLE", latest_only=True)
        assert set(latest["captured_time"]) == {"10:00:00"}
    finally:
        conn.close()


def test_audit_warehouse_detects_duplicate_or_empty_sector(tmp_path):
    conn = _connect_tmp(tmp_path)
    try:
        first = normalize_snapshot_df_for_warehouse(_snapshot_df(), "SAMPLE", imported_file="a.csv")
        duplicate = normalize_snapshot_df_for_warehouse(_snapshot_df(), "SAMPLE", imported_file="b.csv")
        empty = normalize_snapshot_df_for_warehouse(
            pd.DataFrame({"sector_name": [""], "captured_time": ["10:00:00"], "main_net_inflow_billion": [1.0]}),
            "SAMPLE",
            imported_file="empty.csv",
        )
        insert_snapshot_rows(conn, pd.concat([first, duplicate, empty], ignore_index=True))
        audit = audit_warehouse(conn)
        assert audit["duplicate_row_count"] >= 2
        assert audit["empty_sector_name_count"] >= 1
        assert audit["warning_count"] >= 1
    finally:
        conn.close()


def test_summarize_warehouse_status_outputs_chinese_text(tmp_path):
    conn = _connect_tmp(tmp_path)
    try:
        summary = query_warehouse_summary(conn)
        audit = audit_warehouse(conn)
        text = summarize_warehouse_status(summary, audit)
        assert "SQLite warehouse" in text
        assert validate_warehouse_text(text) == []
    finally:
        conn.close()


def test_validate_warehouse_text_detects_forbidden_words():
    hits = validate_warehouse_text("建议买入并加仓")
    assert "买入" in hits
    assert "加仓" in hits
