import pandas as pd

from src.theme_radar import (
    build_market_temperature,
    build_theme_radar_snapshot,
    compare_strict_and_breadth,
)


def _theme(name, value, status):
    return {
        "theme_name": name,
        "sector_name": name,
        "main_net_inflow_billion": value,
        "theme_status": status,
        "theme_status_level": "x",
        "change_pct": 1.0,
        "main_net_ratio": 2.0,
        "used_sectors": name,
        "source_sectors": name,
        "used_sector_count": 1,
        "source_sector_count": 1,
        "aggregation_mode": "strict_representative",
        "theme_value_label": "严格代表口径",
        "match_strategy": "primary_exact",
    }


def test_build_theme_radar_snapshot_adds_label_reason_and_priority():
    df = pd.DataFrame([_theme("新能源链", 40, "强流入"), _theme("半导体/芯片链", -40, "强流出")])
    radar = build_theme_radar_snapshot(df)
    assert {"radar_label", "radar_reason", "radar_priority"}.issubset(radar.columns)
    assert "资金强流入" in radar["radar_label"].tolist()
    assert radar["radar_reason"].str.len().min() > 0


def test_market_temperature_scores_statuses():
    df = pd.DataFrame(
        [
            _theme("A", 40, "强流入"),
            _theme("B", 10, "弱流入"),
            _theme("C", 0, "分歧/中性"),
            _theme("D", -10, "弱流出"),
            _theme("E", -40, "强流出"),
        ]
    )
    temp = build_market_temperature(df)
    assert temp["net_theme_score"] == 0
    assert temp["positive_count"] == 2
    assert temp["negative_count"] == 2
    assert temp["neutral_count"] == 1
    assert temp["market_temperature_label"] == "主题资金分化"


def test_compare_strict_and_breadth_divergence_types():
    strict = pd.DataFrame(
        [
            _theme("A", 10, "弱流入"),
            _theme("B", -10, "弱流出"),
            _theme("C", 10, "弱流入"),
            _theme("D", -10, "弱流出"),
        ]
    )
    breadth = pd.DataFrame(
        [
            _theme("A", 20, "弱流入"),
            _theme("B", -20, "弱流出"),
            _theme("C", -20, "弱流出"),
            _theme("D", 20, "弱流入"),
        ]
    )
    out = compare_strict_and_breadth(strict, breadth).set_index("theme_name")
    assert out.loc["A", "divergence_type"] == "both_inflow"
    assert out.loc["B", "divergence_type"] == "both_outflow"
    assert out.loc["C", "divergence_type"] == "core_inflow_breadth_outflow"
    assert out.loc["D", "divergence_type"] == "core_outflow_breadth_inflow"


def test_radar_reason_has_no_advice_words():
    df = pd.DataFrame([_theme("AI算力/TMT", 10, "弱流入")])
    reason = build_theme_radar_snapshot(df).loc[0, "radar_reason"]
    for word in ["买入", "卖出", "加仓", "减仓"]:
        assert word not in reason

