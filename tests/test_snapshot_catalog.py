from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.snapshot_catalog import (
    build_snapshot_catalog,
    get_snapshot_summary,
    infer_view_data_status,
    list_snapshot_files,
    load_snapshot_by_date,
    parse_snapshot_date,
)


def _write_snapshot(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _rows(snapshot_date: str, times: list[str], sector_type: str = "行业资金流") -> list[dict]:
    rows = []
    for idx, captured_time in enumerate(times):
        rows.append(
            {
                "trade_date": snapshot_date,
                "captured_at": f"{snapshot_date} {captured_time}",
                "captured_time": captured_time,
                "sector_type": sector_type,
                "sector_code": f"{idx:03d}",
                "sector_name": "半导体" if sector_type == "行业资金流" else "人工智能",
                "main_net_inflow_billion": float(idx + 1),
                "main_net_inflow_yuan": float(idx + 1) * 100_000_000,
                "source": "AKShare / Eastmoney",
            }
        )
    return rows


def test_parse_snapshot_date() -> None:
    assert parse_snapshot_date(Path("sector_flow_2026-06-01.csv")) == "2026-06-01"
    assert parse_snapshot_date(Path("bad_2026-06-01.csv")) is None


def test_list_snapshot_files_sorted_desc(tmp_path: Path) -> None:
    (tmp_path / "sector_flow_2026-06-01.csv").write_text("", encoding="utf-8")
    (tmp_path / "sector_flow_2026-06-03.csv").write_text("", encoding="utf-8")
    (tmp_path / "other.csv").write_text("", encoding="utf-8")

    files = list_snapshot_files(str(tmp_path))

    assert [path.name for path in files] == [
        "sector_flow_2026-06-03.csv",
        "sector_flow_2026-06-01.csv",
    ]


def test_build_snapshot_catalog_counts_and_quality(tmp_path: Path) -> None:
    rows = _rows("2026-06-01", ["09:30:00", "09:35:00"])
    rows += _rows("2026-06-01", ["09:30:00"], sector_type="概念资金流")
    _write_snapshot(tmp_path / "sector_flow_2026-06-01.csv", rows)

    catalog = build_snapshot_catalog(str(tmp_path))
    item = catalog.iloc[0]

    assert item["row_count"] == 3
    assert item["captured_time_count"] == 2
    assert item["industry_rows"] == 2
    assert item["concept_rows"] == 1
    assert item["quality_label"] == "快照可回放"


def test_load_snapshot_by_date_missing_returns_empty(tmp_path: Path) -> None:
    assert load_snapshot_by_date("2026-06-01", str(tmp_path)).empty


def test_get_snapshot_summary_counts_sector_types() -> None:
    df = pd.DataFrame(
        _rows("2026-06-01", ["09:30:00", "09:35:00"])
        + _rows("2026-06-01", ["09:30:00"], sector_type="概念资金流")
    )

    summary = get_snapshot_summary(df)

    assert summary["row_count"] == 3
    assert summary["captured_time_count"] == 2
    assert summary["industry_rows"] == 2
    assert summary["concept_rows"] == 1
    assert summary["has_industry_data"] is True
    assert summary["has_concept_data"] is True


def test_infer_view_data_status() -> None:
    assert infer_view_data_status("2026-06-03", "2026-06-03", "LIVE", False) == "LIVE"
    assert infer_view_data_status("2026-06-03", "2026-06-03", "CACHE", False) == "CACHE"
    assert infer_view_data_status("2026-06-01", "2026-06-03", "CACHE", False) == "HISTORY"
    assert infer_view_data_status("2026-06-03", "2026-06-03", "CACHE", False, True) == "HISTORY"
    assert infer_view_data_status("2026-06-03", "2026-06-03", "LIVE", True) == "DEMO"
    assert infer_view_data_status("", "2026-06-03", "CACHE", False) == "EMPTY"


def test_build_snapshot_catalog_bad_csv_does_not_crash(tmp_path: Path) -> None:
    (tmp_path / "sector_flow_2026-06-01.csv").write_text('"unterminated\n', encoding="utf-8")

    catalog = build_snapshot_catalog(str(tmp_path))

    assert len(catalog) == 1
    assert bool(catalog.iloc[0]["is_readable"]) is False
    assert catalog.iloc[0]["quality_label"] == "文件异常"


def test_quality_label_rules(tmp_path: Path) -> None:
    _write_snapshot(tmp_path / "sector_flow_2026-06-01.csv", _rows("2026-06-01", ["09:30:00"]))
    _write_snapshot(
        tmp_path / "sector_flow_2026-06-02.csv",
        _rows("2026-06-02", [f"09:{minute:02d}:00" for minute in range(30, 40)]),
    )
    _write_snapshot(tmp_path / "sector_flow_2026-06-03.csv", _rows("2026-06-03", ["09:30:00"], "概念资金流"))

    catalog = build_snapshot_catalog(str(tmp_path)).set_index("snapshot_date")

    assert catalog.loc["2026-06-01", "quality_label"] == "仅单点快照"
    assert catalog.loc["2026-06-02", "quality_label"] == "快照较完整"
    assert catalog.loc["2026-06-03", "quality_label"] == "缺少行业资金流"
