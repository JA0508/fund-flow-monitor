import pandas as pd

from src.theme_pool import (
    apply_theme_pool_to_ticks,
    build_theme_snapshot,
    build_theme_snapshot_with_trace,
    classify_theme_status,
    map_to_theme,
)
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


def test_strict_representative_uses_only_primary_exact():
    latest = pd.DataFrame([_row("半导体", 10.0), _row("半导体设备", -4.0), _row("半导体材料", -3.0)])
    themed = build_theme_snapshot(latest, theme_mode="strict_representative")
    row = themed[themed["sector_name"].eq("半导体/芯片链")].iloc[0]
    assert row["main_net_inflow_billion"] == 10.0
    assert row["used_sectors"] == "半导体"
    assert "半导体设备" not in row["used_sectors"]
    assert "半导体材料" not in row["used_sectors"]
    assert row["match_strategy"] == "primary_exact"
    assert row["theme_value_label"] == "严格代表口径"


def test_strict_representative_related_exact_fallback_is_marked():
    latest = pd.DataFrame([_row("半导体设备", -4.0), _row("半导体材料", -3.0)])
    themed = build_theme_snapshot(latest, theme_mode="strict_representative")
    row = themed[themed["sector_name"].eq("半导体/芯片链")].iloc[0]
    assert row["main_net_inflow_billion"] == -7.0
    assert "半导体设备" in row["used_sectors"]
    assert row["match_strategy"] == "related_exact_fallback"
    assert row["theme_value_label"] == "严格代表口径-相关替代"


def test_representative_prefers_primary_exact_then_fallback():
    with_primary = pd.DataFrame([_row("半导体", 10.0), _row("半导体设备", -4.0)])
    themed = build_theme_snapshot(with_primary, theme_mode="representative")
    row = themed[themed["sector_name"].eq("半导体/芯片链")].iloc[0]
    assert row["main_net_inflow_billion"] == 10.0
    assert row["used_sectors"] == "半导体"
    assert row["match_strategy"] == "primary_exact"

    without_primary = pd.DataFrame([_row("半导体设备", -4.0)])
    fallback = build_theme_snapshot(without_primary, theme_mode="representative")
    row = fallback[fallback["sector_name"].eq("半导体/芯片链")].iloc[0]
    assert row["main_net_inflow_billion"] == -4.0
    assert row["used_sectors"] == "半导体设备"
    assert row["match_strategy"] == "related_exact_fallback"


def test_breadth_uses_primary_and_related_as_observation_strength():
    latest = pd.DataFrame([_row("半导体", 10.0), _row("半导体设备", -4.0)])
    themed = build_theme_snapshot(latest, theme_mode="breadth")
    row = themed[themed["sector_name"].eq("半导体/芯片链")].iloc[0]
    assert row["main_net_inflow_billion"] == 6.0
    assert "半导体" in row["used_sectors"]
    assert "半导体设备" in row["used_sectors"]
    assert row["source_sectors"] == row["used_sectors"]
    assert row["match_strategy"] == "breadth_all"
    assert row["theme_value_label"] == "观察强度"


def test_theme_snapshot_with_trace_matches_canonical_strict_result():
    latest = pd.DataFrame([_row("半导体", 10.0), _row("半导体设备", -4.0), _row("半导体材料", -3.0)])
    themed = build_theme_snapshot(latest, theme_mode="strict_representative")
    traced, traces = build_theme_snapshot_with_trace(latest, theme_mode="strict_representative")
    row = themed[themed["sector_name"].eq("半导体/芯片链")].iloc[0]
    traced_row = traced[traced["sector_name"].eq("半导体/芯片链")].iloc[0]
    trace = traces["半导体/芯片链"]
    assert traced_row["main_net_inflow_billion"] == row["main_net_inflow_billion"]
    assert trace["aggregate_value"] == row["main_net_inflow_billion"]
    assert trace["derived_state"] == row["theme_status"]
    assert trace["used_member_count"] == 1
    assert [item["member_name"] for item in trace["all_members"] if item["included"]] == ["半导体"]
    assert any(item["exclusion_reason"] == "当前口径未纳入该匹配成员" for item in trace["all_members"])
    included = [item for item in trace["all_members"] if item["included"]][0]
    assert included["canonical_member"] == "半导体"
    assert included["matched_by"] == "canonical_exact"
    assert included["mapping_method"] == "manual_domain_mapping"


def test_theme_snapshot_with_trace_representative_and_breadth_inputs():
    latest = pd.DataFrame([_row("计算机设备", 8.0), _row("软件开发", 3.0), _row("通信", -2.0)])
    representative, representative_traces = build_theme_snapshot_with_trace(latest, theme_mode="representative")
    rep_trace = representative_traces["AI算力/TMT"]
    assert not representative.empty
    assert rep_trace["match_strategy"] in {"primary_exact", "primary_contains", "related_exact_fallback", "related_contains_fallback"}
    assert rep_trace["used_member_count"] >= 1

    breadth, breadth_traces = build_theme_snapshot_with_trace(latest, theme_mode="breadth")
    breadth_trace = breadth_traces["AI算力/TMT"]
    assert breadth_trace["match_strategy"] == "breadth_all"
    assert breadth_trace["aggregate_value"] == breadth[breadth["theme_name"].eq("AI算力/TMT")]["main_net_inflow_billion"].iloc[0]
    assert breadth_trace["used_member_count"] >= rep_trace["used_member_count"]


def test_theme_snapshot_trace_includes_thresholds_and_unmatched_members():
    latest = pd.DataFrame([_row("半导体", 40.0)])
    _, traces = build_theme_snapshot_with_trace(latest, theme_mode="strict_representative")
    trace = traces["半导体/芯片链"]
    assert trace["derived_state"] == "强流入"
    assert any(item["status"] == "强流入" and item["lower_bound"] == 30.0 for item in trace["thresholds"])
    assert trace["unmatched_member_count"] >= 1
    assert all("mapping_source" in item for item in trace["all_members"])


def test_apply_theme_pool_to_ticks_keeps_all_captured_times():
    ticks = pd.DataFrame(
        [
            _row("计算机", 5.0, captured_time="10:00:00"),
            _row("软件开发", 7.0, captured_time="10:00:00"),
            _row("计算机", 8.0, captured_time="10:05:00"),
            _row("软件开发", 9.0, captured_time="10:05:00"),
        ]
    )
    themed = apply_theme_pool_to_ticks(ticks, theme_mode="strict_representative")
    assert themed["captured_time"].nunique() == 2
    assert set(themed["main_net_inflow_billion"]) == {5.0, 8.0}
    assert themed["used_sectors"].drop_duplicates().tolist() == ["计算机"]
    assert themed["source_sectors"].str.contains("软件开发").all()


def test_classify_theme_status_thresholds():
    assert classify_theme_status({"main_net_inflow_billion": 40}) == ("强流入", "positive_strong")
    assert classify_theme_status({"main_net_inflow_billion": 10}) == ("弱流入", "positive_weak")
    assert classify_theme_status({"main_net_inflow_billion": 0}) == ("分歧/中性", "neutral")
    assert classify_theme_status({"main_net_inflow_billion": -10}) == ("弱流出", "negative_weak")
    assert classify_theme_status({"main_net_inflow_billion": -40}) == ("强流出", "negative_strong")


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
