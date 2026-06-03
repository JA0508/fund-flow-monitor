import pandas as pd

from src.intraday_hotspots import (
    build_intraday_hotspot_pool,
    build_intraday_hotspot_summary,
    build_theme_intraday_history,
    calculate_intraday_theme_metrics,
    classify_intraday_hotspot,
    split_hotspot_sections,
)


FORBIDDEN = ["买入", "卖出", "加仓", "减仓", "抄底", "逃顶", "推荐买", "建议买", "建仓", "清仓"]


def _tick(name, value, captured_time):
    return {
        "trade_date": "2026-06-01",
        "captured_at": f"2026-06-01 {captured_time}",
        "captured_time": captured_time,
        "sector_type": "行业资金流",
        "sector_name": name,
        "main_net_inflow_billion": value,
        "change_pct": 1.0,
        "main_net_ratio": 2.0,
        "leading_stock": f"{name}龙头",
        "source": "AKShare / Eastmoney",
    }


def test_build_theme_intraday_history_from_multi_time_ticks():
    ticks = pd.DataFrame(
        [
            _tick("半导体", -10, "10:00:00"),
            _tick("计算机", 5, "10:00:00"),
            _tick("半导体", 15, "10:05:00"),
            _tick("计算机", 8, "10:05:00"),
        ]
    )
    history = build_theme_intraday_history(ticks, mode="strict_representative")
    assert history["captured_time"].nunique() == 2
    assert {"半导体/芯片链", "AI算力/TMT"}.issubset(set(history["theme_name"]))


def test_calculate_intraday_theme_metrics_values_ratios_and_rank_change():
    history = pd.DataFrame(
        [
            {"captured_time": "10:00:00", "theme_name": "A", "main_net_inflow_billion": 1, "theme_status": "弱流入"},
            {"captured_time": "10:00:00", "theme_name": "B", "main_net_inflow_billion": 5, "theme_status": "弱流入"},
            {"captured_time": "10:05:00", "theme_name": "A", "main_net_inflow_billion": 10, "theme_status": "弱流入"},
            {"captured_time": "10:05:00", "theme_name": "B", "main_net_inflow_billion": -2, "theme_status": "分歧/中性"},
        ]
    )
    metrics = calculate_intraday_theme_metrics(history).set_index("theme_name")
    assert metrics.loc["A", "first_value"] == 1
    assert metrics.loc["A", "latest_value"] == 10
    assert metrics.loc["A", "value_change"] == 9
    assert metrics.loc["A", "positive_ratio"] == 1
    assert metrics.loc["B", "negative_ratio"] == 0.5
    assert metrics.loc["A", "rank_change"] == 1


def test_classify_intraday_hotspot_all_types():
    cases = [
        ({"latest_value": 40, "positive_ratio": 0.8}, "persistent_inflow"),
        ({"latest_value": 10, "value_change": 35, "rank_change": 0}, "improving"),
        ({"first_value": -1, "latest_value": 6, "value_change": 7, "rank_change": 0}, "reversal_to_inflow"),
        ({"latest_value": -40, "negative_ratio": 0.8}, "persistent_outflow"),
        ({"latest_value": -10, "value_change": -35, "rank_change": 0}, "worsening"),
        ({"latest_value": 1, "value_change": 0, "rank_change": 0}, "neutral_watch"),
    ]
    for row, expected in cases:
        assert classify_intraday_hotspot(pd.Series(row))[0] == expected


def test_build_pool_sections_summary_and_reasons_are_safe():
    metrics = pd.DataFrame(
        [
            {"theme_name": "A", "first_value": -1, "latest_value": 6, "value_change": 7, "abs_value_change": 7, "rank_change": 0, "positive_ratio": 0.5, "negative_ratio": 0.5, "latest_status": "弱流入"},
            {"theme_name": "B", "first_value": 0, "latest_value": 40, "value_change": 40, "abs_value_change": 40, "rank_change": 0, "positive_ratio": 1.0, "negative_ratio": 0, "latest_status": "强流入"},
            {"theme_name": "C", "first_value": 20, "latest_value": -20, "value_change": -40, "abs_value_change": 40, "rank_change": 0, "positive_ratio": 0.5, "negative_ratio": 0.5, "latest_status": "弱流出"},
            {"theme_name": "D", "first_value": 0, "latest_value": 1, "value_change": 1, "abs_value_change": 1, "rank_change": 0, "positive_ratio": 0.5, "negative_ratio": 0, "latest_status": "分歧/中性"},
        ]
    )
    pool = build_intraday_hotspot_pool(metrics, top_n=10)
    assert {"hotspot_type", "hotspot_label", "hotspot_reason", "display_priority"}.issubset(pool.columns)
    sections = split_hotspot_sections(pool)
    assert not sections["positive_hotspots"].empty
    assert not sections["pressure_hotspots"].empty
    summary = build_intraday_hotspot_summary(pool)
    assert summary["summary_label"] in {"日内热点偏活跃", "日内热点偏承压", "日内热点分化"}
    assert summary["summary_reason"]
    text = " ".join(pool["hotspot_reason"].tolist() + [summary["summary_reason"]])
    for word in FORBIDDEN:
        assert word not in text


def test_single_snapshot_does_not_crash():
    ticks = pd.DataFrame([_tick("半导体", 10, "10:00:00")])
    history = build_theme_intraday_history(ticks, mode="strict_representative")
    metrics = calculate_intraday_theme_metrics(history)
    pool = build_intraday_hotspot_pool(metrics)
    assert history["captured_time"].nunique() == 1
    assert not pool.empty
