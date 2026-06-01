import pandas as pd

from src.theme_concepts import build_theme_concept_summary, map_concepts_to_theme


FORBIDDEN = ["买入", "卖出", "加仓", "减仓", "抄底", "逃顶"]


def _concept(name, value):
    return {
        "sector_name": name,
        "main_net_inflow_billion": value,
        "change_pct": 1.0,
        "main_net_ratio": 2.0,
        "leading_stock": f"{name}龙头",
    }


def test_ai_concept_maps_to_tmt_theme():
    df = pd.DataFrame([_concept("人工智能", 10), _concept("锂电池", 5)])
    matched = map_concepts_to_theme(df, "AI算力/TMT")
    assert matched["sector_name"].tolist() == ["人工智能"]


def test_lithium_battery_maps_to_new_energy():
    df = pd.DataFrame([_concept("锂电池", 5)])
    matched = map_concepts_to_theme(df, "新能源链")
    assert matched["sector_name"].tolist() == ["锂电池"]


def test_lithography_maps_to_semiconductor():
    df = pd.DataFrame([_concept("光刻机", -8)])
    matched = map_concepts_to_theme(df, "半导体/芯片链")
    assert matched["sector_name"].tolist() == ["光刻机"]


def test_theme_concept_summary_keeps_concept_value_separate_from_theme_main_value():
    concept_df = pd.DataFrame([_concept("锂电池", 7), _concept("光伏", 8)])
    summary = build_theme_concept_summary(concept_df, ["新能源链"])
    row = summary.iloc[0]
    assert row["concept_net_inflow_billion"] == 15
    assert "main_net_inflow_billion" not in summary.columns
    assert row["concept_status"] == "相关概念流入"


def test_concept_reason_has_no_advice_words():
    concept_df = pd.DataFrame([_concept("人工智能", 30)])
    reason = build_theme_concept_summary(concept_df, ["AI算力/TMT"]).iloc[0]["concept_reason"]
    for word in FORBIDDEN:
        assert word not in reason
