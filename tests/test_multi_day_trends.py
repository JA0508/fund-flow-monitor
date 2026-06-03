from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.multi_day_trends import (
    build_daily_theme_snapshots,
    build_multi_day_trend_pool,
    build_multi_day_trend_summary,
    calculate_multi_day_theme_metrics,
    classify_multi_day_trend,
    split_multi_day_trend_sections,
)
from src.snapshot_catalog import build_snapshot_catalog


FORBIDDEN = ["买入", "卖出", "加仓", "减仓", "抄底", "逃顶", "推荐买", "建议买", "建仓", "清仓"]


def _tick(snapshot_date: str, sector_name: str, value: float, captured_time: str = "15:00:00") -> dict:
    return {
        "trade_date": snapshot_date,
        "captured_at": f"{snapshot_date} {captured_time}",
        "captured_time": captured_time,
        "sector_type": "行业资金流",
        "sector_name": sector_name,
        "sector_code": sector_name,
        "main_net_inflow_billion": value,
        "main_net_inflow_yuan": value * 100_000_000,
        "change_pct": 1.0,
        "main_net_ratio": 2.0,
        "leading_stock": f"{sector_name}龙头",
        "source": "AKShare / Eastmoney",
    }


def _write_snapshot(root: Path, snapshot_date: str, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(root / f"sector_flow_{snapshot_date}.csv", index=False)


def test_build_daily_theme_snapshots_from_multiple_dates(tmp_path: Path) -> None:
    _write_snapshot(
        tmp_path,
        "2026-06-01",
        [_tick("2026-06-01", "半导体", -10), _tick("2026-06-01", "计算机", 5)],
    )
    _write_snapshot(
        tmp_path,
        "2026-06-02",
        [_tick("2026-06-02", "半导体", 40), _tick("2026-06-02", "计算机", 10)],
    )
    catalog = build_snapshot_catalog(str(tmp_path))

    daily = build_daily_theme_snapshots(catalog, data_dir=str(tmp_path), mode="strict_representative")

    assert daily["snapshot_date"].nunique() == 2
    assert {"半导体/芯片链", "AI算力/TMT"}.issubset(set(daily["theme_name"]))
    assert {"snapshot_date", "captured_time", "quality_label", "mode"}.issubset(daily.columns)


def test_calculate_multi_day_theme_metrics_values_and_ratios() -> None:
    daily = pd.DataFrame(
        [
            {"snapshot_date": "2026-06-01", "theme_name": "A", "main_net_inflow_billion": -10, "theme_status": "弱流出"},
            {"snapshot_date": "2026-06-02", "theme_name": "A", "main_net_inflow_billion": 20, "theme_status": "弱流入"},
            {"snapshot_date": "2026-06-01", "theme_name": "B", "main_net_inflow_billion": 1, "theme_status": "分歧/中性"},
            {"snapshot_date": "2026-06-02", "theme_name": "B", "main_net_inflow_billion": -20, "theme_status": "弱流出"},
        ]
    )

    metrics = calculate_multi_day_theme_metrics(daily).set_index("theme_name")

    assert metrics.loc["A", "first_value"] == -10
    assert metrics.loc["A", "latest_value"] == 20
    assert metrics.loc["A", "value_change"] == 30
    assert metrics.loc["A", "positive_ratio"] == 0.5
    assert metrics.loc["A", "negative_ratio"] == 0.5
    assert metrics.loc["B", "neutral_day_count"] == 1


def test_classify_multi_day_trend_all_types() -> None:
    cases = [
        ({"latest_value": 40, "positive_ratio": 0.8}, "persistent_strength"),
        ({"first_value": 0, "latest_value": 35, "value_change": 35, "positive_ratio": 0.5}, "improving_trend"),
        ({"first_value": -10, "latest_value": 8, "value_change": 18}, "reversal_to_strength"),
        ({"latest_value": -40, "negative_ratio": 0.8}, "persistent_pressure"),
        ({"first_value": 20, "latest_value": -20, "value_change": -40}, "weakening_trend"),
        ({"first_value": 1, "latest_value": 2, "value_change": 1}, "mixed_trend"),
    ]
    for row, expected in cases:
        assert classify_multi_day_trend(pd.Series(row))[0] == expected


def test_build_pool_sections_summary_and_reasons_are_safe() -> None:
    metrics = pd.DataFrame(
        [
            {"theme_name": "A", "date_count": 2, "first_value": -10, "latest_value": 8, "value_change": 18, "abs_value_change": 18, "positive_ratio": 0.5, "negative_ratio": 0.5, "latest_status": "弱流入"},
            {"theme_name": "B", "date_count": 2, "first_value": 0, "latest_value": 40, "value_change": 40, "abs_value_change": 40, "positive_ratio": 0.5, "negative_ratio": 0, "latest_status": "强流入"},
            {"theme_name": "C", "date_count": 2, "first_value": 20, "latest_value": -20, "value_change": -40, "abs_value_change": 40, "positive_ratio": 0.5, "negative_ratio": 0.5, "latest_status": "弱流出"},
            {"theme_name": "D", "date_count": 2, "first_value": 0, "latest_value": 1, "value_change": 1, "abs_value_change": 1, "positive_ratio": 0, "negative_ratio": 0, "latest_status": "分歧/中性"},
        ]
    )

    pool = build_multi_day_trend_pool(metrics, top_n=10)
    assert {"trend_type", "trend_label", "trend_reason", "display_priority"}.issubset(pool.columns)
    sections = split_multi_day_trend_sections(pool)
    assert not sections["strength_trends"].empty
    assert not sections["pressure_trends"].empty
    summary = build_multi_day_trend_summary(pool)
    assert summary["summary_label"] in {"多日主题结构偏强", "多日主题结构偏弱", "多日主题结构分化"}
    text = " ".join(pool["trend_reason"].tolist() + [summary["summary_reason"]])
    for word in FORBIDDEN:
        assert word not in text


def test_single_available_date_does_not_crash(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, "2026-06-01", [_tick("2026-06-01", "半导体", 10)])
    catalog = build_snapshot_catalog(str(tmp_path))

    daily = build_daily_theme_snapshots(catalog, data_dir=str(tmp_path))
    metrics = calculate_multi_day_theme_metrics(daily)
    pool = build_multi_day_trend_pool(metrics)

    assert daily["snapshot_date"].nunique() == 1
    assert not metrics.empty
    assert not pool.empty
