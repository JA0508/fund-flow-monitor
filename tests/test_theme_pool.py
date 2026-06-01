import pandas as pd

from src.theme_pool import apply_theme_pool_to_ticks, build_theme_snapshot, map_to_theme
from src.ui_components import filter_rank_rows
from tools.verify_runtime import detect_demo_contamination


def _row(name, value, captured_time="10:00:00", stock=None, source="AKShare / Eastmoney"):
    return {
        "trade_date": "2026-06-01",
        "captured_at": f"2026-06-01 {captured_time}",
        "captured_time": captured_time,
        "sector_type": "行业资金流",
        "sector_name": name,
        "change_pct": 1.0,
        "main_net_inflow_billion": value,
        "main_net_ratio": 2.0,
        "leading_stock": stock or f"{name}龙头",
        "source": source,
    }


def test_simulated_chip_design_name_is_not_demo_contamination():
    df = pd.DataFrame([_row("模拟芯片设计", 1.0)])
    assert detect_demo_contamination(df) is False
    assert map_to_theme("模拟芯片设计") == "半导体/芯片链"


def test_map_to_theme_primary_related_and_unknown():
    assert map_to_theme("半导体") == "半导体/芯片链"
    assert map_to_theme("半导体设备") == "半导体/芯片链"
    assert map_to_theme("IT服务Ⅱ") == "AI算力/TMT"
    assert map_to_theme("电力") == "红利防御"
    assert map_to_theme("未知板块") is None


def test_representative_uses_primary_not_related_when_primary_exists():
    latest = pd.DataFrame([_row("半导体", 10.0, stock="A"), _row("半导体设备", -4.0, stock="B")])
    themed = build_theme_snapshot(latest, theme_mode="representative")
    assert len(themed) == 1
    assert themed.loc[0, "sector_name"] == "半导体/芯片链"
    assert themed.loc[0, "main_net_inflow_billion"] == 10.0
    assert themed.loc[0, "used_sectors"] == "半导体"
    assert "半导体设备" in themed.loc[0, "source_sectors"]
    assert themed.loc[0, "aggregation_mode"] == "representative"
    assert themed.loc[0, "theme_value_label"] == "代表口径"


def test_breadth_uses_primary_and_related_as_observation_strength():
    latest = pd.DataFrame([_row("半导体", 10.0, stock="A"), _row("半导体设备", -4.0, stock="B")])
    themed = build_theme_snapshot(latest, theme_mode="breadth")
    assert len(themed) == 1
    assert themed.loc[0, "main_net_inflow_billion"] == 6.0
    assert "半导体" in themed.loc[0, "used_sectors"]
    assert "半导体设备" in themed.loc[0, "used_sectors"]
    assert themed.loc[0, "source_sectors"] == themed.loc[0, "used_sectors"]
    assert themed.loc[0, "aggregation_mode"] == "breadth"
    assert themed.loc[0, "theme_value_label"] == "观察强度"


def test_apply_theme_pool_to_ticks_representative_keeps_all_captured_times():
    ticks = pd.DataFrame(
        [
            _row("计算机", 5.0, captured_time="10:00:00"),
            _row("软件开发", 7.0, captured_time="10:00:00"),
            _row("计算机", 8.0, captured_time="10:05:00"),
            _row("软件开发", 9.0, captured_time="10:05:00"),
        ]
    )
    themed = apply_theme_pool_to_ticks(ticks, theme_mode="representative")
    assert themed["captured_time"].nunique() == 2
    assert set(themed["main_net_inflow_billion"]) == {5.0, 8.0}
    assert themed["used_sectors"].drop_duplicates().tolist() == ["计算机"]
    assert themed["source_sectors"].str.contains("软件开发").all()


def test_apply_theme_pool_to_ticks_breadth_sums_related_history():
    ticks = pd.DataFrame(
        [
            _row("计算机", 5.0, captured_time="10:00:00"),
            _row("软件开发", 7.0, captured_time="10:00:00"),
            _row("软件开发", 9.0, captured_time="10:05:00"),
        ]
    )
    themed = apply_theme_pool_to_ticks(ticks, theme_mode="breadth")
    first = themed[themed["captured_time"].eq("10:00:00")].iloc[0]
    second = themed[themed["captured_time"].eq("10:05:00")].iloc[0]
    assert first["main_net_inflow_billion"] == 12.0
    assert second["main_net_inflow_billion"] == 9.0
    assert second["used_sectors"] == "软件开发"


def test_rank_filters_keep_positive_and_negative_separate():
    df = pd.DataFrame(
        [
            {"sector_name": "A", "main_net_inflow_billion": 3.0},
            {"sector_name": "B", "main_net_inflow_billion": -2.0},
            {"sector_name": "C", "main_net_inflow_billion": 0.0},
        ]
    )
    inflow = filter_rank_rows(df, direction="in")
    outflow = filter_rank_rows(df, direction="out")
    assert inflow["sector_name"].tolist() == ["A"]
    assert outflow["sector_name"].tolist() == ["B"]

