from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.local_warehouse import connect_warehouse, initialize_warehouse, rebuild_warehouse_from_csv_directory
from src.theme_history import (
    build_theme_history_from_sector_history,
    build_theme_history_matrix,
    build_theme_history_quality_report,
    build_theme_status_timeline,
    get_theme_history_mode_options,
    load_sector_history_from_warehouse,
    normalize_theme_history_mode,
    summarize_theme_history,
    summarize_theme_history_quality,
    validate_theme_history_text,
)
from src.theme_taxonomy import load_theme_taxonomy


def _write_theme_history_csv(directory: Path, date_text: str, latest_shift: float = 0.0) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    sectors = ["半导体", "计算机", "电池", "银行", "医药生物", "证券Ⅱ", "食品饮料", "国防军工"]
    for captured_time, multiplier in (("09:30:00", 1.0), ("14:50:00", 2.0)):
        for idx, sector in enumerate(sectors):
            base = ((idx % 4) - 1.5) * 10
            rows.append(
                {
                    "source_type": "行业资金流",
                    "sector_name": sector,
                    "main_net_inflow_billion": base * multiplier + latest_shift,
                    "captured_time": captured_time,
                    "source": "SAMPLE",
                    "trade_date": date_text,
                }
            )
    path = directory / f"sector_flow_{date_text}.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _build_temp_warehouse(tmp_path: Path):
    csv_dir = tmp_path / "ticks"
    _write_theme_history_csv(csv_dir, "2026-01-15")
    _write_theme_history_csv(csv_dir, "2026-01-16", latest_shift=5)
    db_path = tmp_path / "fund_flow.sqlite"
    conn = connect_warehouse(str(db_path))
    initialize_warehouse(conn)
    rebuild_warehouse_from_csv_directory(conn, str(csv_dir), "SAMPLE", clear_source=True)
    return conn


def test_mode_options_and_normalization():
    options = get_theme_history_mode_options()
    assert {"严格代表口径", "代表口径", "广度观察"}.issubset(set(options))
    assert normalize_theme_history_mode(None) == "代表口径"
    assert normalize_theme_history_mode("未知") == "代表口径"
    assert normalize_theme_history_mode("breadth") == "广度观察"


def test_load_sector_history_empty_warehouse(tmp_path: Path):
    conn = connect_warehouse(str(tmp_path / "empty.sqlite"))
    initialize_warehouse(conn)
    try:
        history = load_sector_history_from_warehouse(conn)
    finally:
        conn.close()
    assert history.empty


def test_load_sector_history_reads_sample_rows_and_latest_per_day(tmp_path: Path):
    conn = _build_temp_warehouse(tmp_path)
    try:
        latest = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=True)
        all_rows = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=False)
    finally:
        conn.close()
    assert not latest.empty
    assert set(latest["captured_time"].unique()) == {"14:50:00"}
    assert len(all_rows) > len(latest)


def test_load_sector_history_source_filter_missing_returns_empty(tmp_path: Path):
    conn = _build_temp_warehouse(tmp_path)
    try:
        missing = load_sector_history_from_warehouse(conn, source_type="LOCAL", latest_per_day=True)
    finally:
        conn.close()
    assert missing.empty


def test_load_sector_history_limit_days(tmp_path: Path):
    conn = _build_temp_warehouse(tmp_path)
    try:
        limited = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=True, limit_days=1)
    finally:
        conn.close()
    assert limited["data_date"].nunique() == 1


def test_load_sector_history_date_range(tmp_path: Path):
    conn = _build_temp_warehouse(tmp_path)
    try:
        ranged = load_sector_history_from_warehouse(
            conn,
            source_type="SAMPLE",
            start_date="2026-01-16",
            end_date="2026-01-16",
            latest_per_day=True,
        )
    finally:
        conn.close()
    assert set(ranged["data_date"].unique()) == {"2026-01-16"}


def test_build_theme_history_empty_and_sample(tmp_path: Path):
    taxonomy = load_theme_taxonomy()
    empty = build_theme_history_from_sector_history(pd.DataFrame(), taxonomy)
    assert empty.empty
    conn = _build_temp_warehouse(tmp_path)
    try:
        sector_history = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=True)
    finally:
        conn.close()
    theme_history = build_theme_history_from_sector_history(sector_history, taxonomy, theme_mode="代表口径")
    assert {"theme_name", "data_date", "main_net_inflow_billion"}.issubset(theme_history.columns)
    assert not theme_history.empty
    assert "SAMPLE 合成演示数据" in theme_history["data_status_label"].iloc[0]


def test_build_theme_history_modes_do_not_crash(tmp_path: Path):
    conn = _build_temp_warehouse(tmp_path)
    try:
        sector_history = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=True)
    finally:
        conn.close()
    taxonomy = load_theme_taxonomy()
    strict = build_theme_history_from_sector_history(sector_history, taxonomy, theme_mode="严格代表口径")
    breadth = build_theme_history_from_sector_history(sector_history, taxonomy, theme_mode="广度观察")
    assert not strict.empty
    assert not breadth.empty


def test_theme_history_matrix_and_timeline(tmp_path: Path):
    conn = _build_temp_warehouse(tmp_path)
    try:
        sector_history = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=True)
    finally:
        conn.close()
    theme_history = build_theme_history_from_sector_history(sector_history, load_theme_taxonomy(), theme_mode="代表口径")
    matrix = build_theme_history_matrix(theme_history)
    timeline = build_theme_status_timeline(theme_history)
    assert "data_date" in matrix.columns
    assert "status_change_label" in timeline.columns
    assert not timeline.empty


def test_empty_matrix_and_timeline_are_safe():
    assert build_theme_history_matrix(pd.DataFrame()).empty
    assert build_theme_status_timeline(pd.DataFrame()).empty


def test_timeline_contains_status_change_labels(tmp_path: Path):
    conn = _build_temp_warehouse(tmp_path)
    try:
        sector_history = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=True)
    finally:
        conn.close()
    theme_history = build_theme_history_from_sector_history(sector_history, load_theme_taxonomy(), theme_mode="代表口径")
    timeline = build_theme_status_timeline(theme_history)
    assert timeline["status_change_label"].notna().all()
    assert "样本不足" in set(timeline["status_change_label"])


def test_summarize_theme_history_empty_and_sample(tmp_path: Path):
    empty_summary = summarize_theme_history(pd.DataFrame())
    assert empty_summary["summary_label"] == "暂无主题历史数据"
    conn = _build_temp_warehouse(tmp_path)
    try:
        sector_history = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=True)
    finally:
        conn.close()
    theme_history = build_theme_history_from_sector_history(sector_history, load_theme_taxonomy(), theme_mode="代表口径")
    summary = summarize_theme_history(theme_history)
    assert summary["summary_label"] == "仅 SAMPLE 主题历史可用"
    assert summary["history_available"] is True


def test_summarize_theme_history_top_lists(tmp_path: Path):
    conn = _build_temp_warehouse(tmp_path)
    try:
        sector_history = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=True)
    finally:
        conn.close()
    theme_history = build_theme_history_from_sector_history(sector_history, load_theme_taxonomy(), theme_mode="代表口径")
    summary = summarize_theme_history(theme_history, top_n=3)
    assert len(summary["strongest_latest_themes"]) <= 3
    assert len(summary["pressured_latest_themes"]) <= 3


def test_theme_history_quality_empty_and_duplicate():
    empty_report = build_theme_history_quality_report(pd.DataFrame(), pd.DataFrame())
    assert empty_report["quality_label"] == "暂无主题历史数据"
    theme_history = pd.DataFrame(
        [
            {
                "source_type": "SAMPLE",
                "data_date": "2026-01-15",
                "captured_time": "14:50:00",
                "theme_name": "半导体/芯片链",
                "main_net_inflow_billion": 10,
                "data_status_label": "SAMPLE 合成演示数据",
            },
            {
                "source_type": "SAMPLE",
                "data_date": "2026-01-15",
                "captured_time": "14:50:00",
                "theme_name": "半导体/芯片链",
                "main_net_inflow_billion": 12,
                "data_status_label": "SAMPLE 合成演示数据",
            },
        ]
    )
    report = build_theme_history_quality_report(pd.DataFrame({"x": [1]}), theme_history)
    assert report["duplicate_theme_date_count"] > 0
    assert report["warning_count"] > 0


def test_theme_history_quality_good_sample(tmp_path: Path):
    conn = _build_temp_warehouse(tmp_path)
    try:
        sector_history = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=True)
    finally:
        conn.close()
    theme_history = build_theme_history_from_sector_history(sector_history, load_theme_taxonomy(), theme_mode="代表口径")
    report = build_theme_history_quality_report(sector_history, theme_history)
    assert report["row_count"] == len(theme_history)
    assert report["date_count"] == 2


def test_quality_summary_and_forbidden_words():
    report = {
        "quality_label": "主题历史质量良好",
        "date_count": 2,
        "theme_count": 8,
        "row_count": 16,
    }
    text = summarize_theme_history_quality(report)
    assert "主题历史聚合质量" in text
    assert validate_theme_history_text(text) == []
    assert validate_theme_history_text("趋势确立") == ["趋势确立"]


def test_normal_theme_history_summary_text_has_no_forbidden_words(tmp_path: Path):
    conn = _build_temp_warehouse(tmp_path)
    try:
        sector_history = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=True)
    finally:
        conn.close()
    theme_history = build_theme_history_from_sector_history(sector_history, load_theme_taxonomy(), theme_mode="代表口径")
    summary = summarize_theme_history(theme_history)
    assert validate_theme_history_text(summary["summary_reason"]) == []
