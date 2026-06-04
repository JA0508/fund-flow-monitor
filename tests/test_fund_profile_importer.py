from __future__ import annotations

import pandas as pd

from src.fund_profile_importer import (
    build_profile_summary_from_csv,
    build_profile_theme_exposure_table,
    get_fund_profile_csv_required_columns,
    load_fund_profiles_csv,
    merge_profile_exposure_with_theme_radar,
    normalize_fund_profiles_csv,
    summarize_profile_observations,
    validate_fund_profiles_csv,
    validate_profile_observation_text,
)
from src.theme_taxonomy import load_theme_taxonomy


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "profile_id": "DEMO_TEST",
                "profile_name": "测试主题基金",
                "fund_code": "DEMO-TEST",
                "fund_type": "主题基金",
                "description": "示例配置",
                "theme_name": "半导体/芯片链",
                "exposure_weight": 0.7,
                "exposure_role": "core",
                "notes": "示例",
            },
            {
                "profile_id": "DEMO_TEST",
                "profile_name": "测试主题基金",
                "fund_code": "DEMO-TEST",
                "fund_type": "主题基金",
                "description": "示例配置",
                "theme_name": "AI算力/TMT",
                "exposure_weight": 0.3,
                "exposure_role": "satellite",
                "notes": "示例",
            },
        ]
    )


def test_required_columns() -> None:
    assert get_fund_profile_csv_required_columns() == ["profile_id", "profile_name", "theme_name"]


def test_load_missing_file_does_not_crash(tmp_path) -> None:
    df = load_fund_profiles_csv(str(tmp_path / "missing.csv"))
    assert df.empty
    assert df.attrs.get("warnings")


def test_normalize_fund_profiles_csv_fills_optional_columns() -> None:
    df = pd.DataFrame([{"profile_id": "P1", "profile_name": "组合", "theme_name": "医药"}])
    normalized = normalize_fund_profiles_csv(df)
    assert "fund_code" in normalized.columns
    assert normalized["exposure_weight"].iloc[0] == 1.0


def test_validate_missing_required_columns() -> None:
    report = validate_fund_profiles_csv(pd.DataFrame([{"profile_id": "P1"}]))
    assert report["error_count"] > 0
    assert "缺少必要字段" in " ".join(report["errors"])


def test_validate_unknown_theme() -> None:
    df = pd.DataFrame([{"profile_id": "P1", "profile_name": "组合", "theme_name": "未知主题"}])
    report = validate_fund_profiles_csv(df, load_theme_taxonomy())
    assert "未知主题" in report["unknown_themes"]
    assert report["warning_count"] > 0


def test_validate_negative_weight() -> None:
    df = pd.DataFrame([{"profile_id": "P1", "profile_name": "组合", "theme_name": "医药", "exposure_weight": -0.1}])
    report = validate_fund_profiles_csv(df, load_theme_taxonomy())
    assert report["error_count"] > 0
    assert report["invalid_weight_count"] > 0


def test_validate_weight_greater_than_one() -> None:
    df = pd.DataFrame([{"profile_id": "P1", "profile_name": "组合", "theme_name": "医药", "exposure_weight": 1.5}])
    report = validate_fund_profiles_csv(df, load_theme_taxonomy())
    assert report["warning_count"] > 0


def test_validate_duplicate_profile_theme() -> None:
    df = pd.DataFrame(
        [
            {"profile_id": "P1", "profile_name": "组合", "theme_name": "医药", "exposure_weight": 0.5},
            {"profile_id": "P1", "profile_name": "组合", "theme_name": "医药", "exposure_weight": 0.5},
        ]
    )
    report = validate_fund_profiles_csv(df, load_theme_taxonomy())
    assert report["duplicated_profile_theme_count"] == 2


def test_build_profile_summary_from_csv() -> None:
    report = validate_fund_profiles_csv(_sample_df(), load_theme_taxonomy())
    summary = build_profile_summary_from_csv(_sample_df(), report)
    assert summary["theme_count"].iloc[0] == 2
    assert summary["total_exposure_weight"].iloc[0] == 1.0


def test_build_profile_theme_exposure_table_taxonomy_fields() -> None:
    exposure = build_profile_theme_exposure_table(_sample_df(), load_theme_taxonomy())
    assert exposure["taxonomy_registered"].all()
    assert set(exposure["theme_group"]) == {"科技成长"}


def test_merge_profile_exposure_with_empty_radar() -> None:
    exposure = build_profile_theme_exposure_table(_sample_df(), load_theme_taxonomy())
    merged = merge_profile_exposure_with_theme_radar(exposure, pd.DataFrame())
    assert len(merged) == 2
    assert set(merged["observation_label"]) == {"样本不足"}


def test_merge_profile_exposure_with_radar() -> None:
    exposure = build_profile_theme_exposure_table(_sample_df(), load_theme_taxonomy())
    radar = pd.DataFrame(
        [
            {"theme_name": "半导体/芯片链", "main_net_inflow_billion": 40, "theme_status": "强流入", "match_strategy": "primary_exact", "source_sector_count": 1},
            {"theme_name": "AI算力/TMT", "main_net_inflow_billion": -20, "theme_status": "弱流出", "match_strategy": "primary_exact", "source_sector_count": 2},
        ]
    )
    merged = merge_profile_exposure_with_theme_radar(exposure, radar)
    assert "weighted_theme_score" in merged.columns
    assert merged["weighted_theme_score"].sum() > 0


def test_summarize_profile_observations() -> None:
    exposure = build_profile_theme_exposure_table(_sample_df(), load_theme_taxonomy())
    radar = pd.DataFrame(
        [
            {"theme_name": "半导体/芯片链", "main_net_inflow_billion": 40, "theme_status": "强流入"},
            {"theme_name": "AI算力/TMT", "main_net_inflow_billion": -20, "theme_status": "弱流出"},
        ]
    )
    summary = summarize_profile_observations(merge_profile_exposure_with_theme_radar(exposure, radar))
    assert summary["profile_observation_label"].iloc[0] in {"关注主题资金偏强", "关注主题资金承压", "关注主题资金分化"}


def test_validate_profile_observation_text_hits_forbidden_words() -> None:
    hits = validate_profile_observation_text("这里出现建议买和未来会涨。")
    assert "建议买" in hits
    assert "未来会涨" in hits


def test_sample_csv_observation_text_has_no_forbidden_words() -> None:
    df = load_fund_profiles_csv("sample_data/fund_profiles/sample_fund_profiles.csv")
    exposure = build_profile_theme_exposure_table(df, load_theme_taxonomy())
    radar = pd.DataFrame(
        [
            {"theme_name": "半导体/芯片链", "main_net_inflow_billion": 40, "theme_status": "强流入"},
            {"theme_name": "AI算力/TMT", "main_net_inflow_billion": -40, "theme_status": "强流出"},
            {"theme_name": "新能源链", "main_net_inflow_billion": 0, "theme_status": "分歧/中性"},
        ]
    )
    merged = merge_profile_exposure_with_theme_radar(exposure, radar)
    summary = summarize_profile_observations(merged)
    text = " ".join(merged["observation_reason"].astype(str).tolist() + summary["profile_observation_reason"].astype(str).tolist())
    assert validate_profile_observation_text(text) == []
