import pandas as pd

from src.fund_profiles import (
    build_fund_summary,
    build_fund_theme_exposure,
    build_holding_related_pool,
    load_fund_profiles,
    normalize_fund_theme_weights,
    validate_fund_profile,
)


FORBIDDEN = ["买入", "卖出", "加仓", "减仓", "抄底", "逃顶", "推荐买", "建议买", "建仓", "清仓"]


def _fund():
    return {
        "fund_name": "测试基金",
        "fund_code": "DEMO-TEST",
        "fund_type": "主题基金",
        "themes": [
            {"theme_name": "半导体/芯片链", "weight": 2},
            {"theme_name": "AI算力/TMT", "weight": 1},
        ],
    }


def _theme_radar():
    return pd.DataFrame(
        [
            {
                "theme_name": "半导体/芯片链",
                "main_net_inflow_billion": -40,
                "theme_status": "强流出",
                "theme_status_level": "negative_strong",
                "radar_label": "资金明显流出",
                "radar_reason": "资金承压",
                "theme_value_label": "严格代表口径",
                "match_strategy": "primary_exact",
            },
            {
                "theme_name": "AI算力/TMT",
                "main_net_inflow_billion": 10,
                "theme_status": "弱流入",
                "theme_status_level": "positive_weak",
                "radar_label": "资金小幅流入",
                "radar_reason": "资金略偏强",
                "theme_value_label": "严格代表口径",
                "match_strategy": "primary_exact",
            },
        ]
    )


def test_missing_config_returns_default_fund_profile(tmp_path):
    profile = load_fund_profiles(str(tmp_path / "missing.json"))
    assert profile["profile_name"] == "默认基金关注组合"
    assert profile["funds"][0]["fund_code"].startswith("DEMO")
    assert "_load_warning" in profile


def test_damaged_config_returns_default_fund_profile(tmp_path):
    path = tmp_path / "fund_profiles.json"
    path.write_text("{bad json", encoding="utf-8")
    profile = load_fund_profiles(str(path))
    assert profile["profile_name"] == "默认基金关注组合"
    assert "_load_warning" in profile


def test_validate_fund_profile_warns_when_weights_not_close_to_one():
    profile = {"funds": [_fund()]}
    warnings = validate_fund_profile(profile)
    assert any("归一化" in warning for warning in warnings)


def test_normalize_fund_theme_weights_normalizes_without_mutating_json():
    fund = _fund()
    normalized = normalize_fund_theme_weights(fund)
    weights = [item["normalized_weight"] for item in normalized["themes"]]
    assert round(sum(weights), 6) == 1
    assert fund["themes"][0]["weight"] == 2


def test_build_fund_theme_exposure_outputs_expected_columns():
    exposure = build_fund_theme_exposure([_fund()])
    assert {
        "fund_name",
        "fund_code",
        "fund_type",
        "theme_name",
        "raw_weight",
        "normalized_weight",
    }.issubset(exposure.columns)
    assert len(exposure) == 2


def test_build_holding_related_pool_merges_exposure_and_theme_radar():
    exposure = build_fund_theme_exposure([_fund()])
    pool = build_holding_related_pool(exposure, _theme_radar())
    assert len(pool) == 2
    semi = pool[pool["theme_name"].eq("半导体/芯片链")].iloc[0]
    assert round(semi["holding_impact_score"], 4) == round((2 / 3) * -2, 4)
    assert semi["holding_impact_label"] == "相关主题明显承压"


def test_build_fund_summary_groups_by_fund():
    exposure = build_fund_theme_exposure([_fund()])
    pool = build_holding_related_pool(exposure, _theme_radar())
    summary = build_fund_summary(pool)
    assert len(summary) == 1
    assert summary.iloc[0]["fund_code"] == "DEMO-TEST"
    assert "半导体/芯片链" in summary.iloc[0]["top_negative_themes"]


def test_holding_reasons_have_no_advice_words():
    exposure = build_fund_theme_exposure([_fund()])
    pool = build_holding_related_pool(exposure, _theme_radar())
    summary = build_fund_summary(pool)
    text = " ".join(pool["holding_impact_reason"].tolist() + summary["summary_reason"].tolist())
    for word in FORBIDDEN:
        assert word not in text
