from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.theme_radar import STATUS_SCORE
from src.theme_taxonomy import build_theme_definition_table, get_theme_names, load_theme_taxonomy


SAMPLE_FUND_PROFILE_CSV = "sample_data/fund_profiles/sample_fund_profiles.csv"
REQUIRED_COLUMNS = ["profile_id", "profile_name", "theme_name"]
OPTIONAL_COLUMNS = [
    "fund_code",
    "fund_type",
    "description",
    "exposure_weight",
    "exposure_role",
    "notes",
]
OUTPUT_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
FORBIDDEN_PROFILE_TEXT = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "抄底",
    "逃顶",
    "推荐买",
    "推荐卖",
    "建议买",
    "建议卖",
    "建仓",
    "清仓",
    "未来会涨",
    "未来会跌",
    "适合配置",
    "应该调仓",
)


def get_fund_profile_csv_required_columns() -> list[str]:
    return list(REQUIRED_COLUMNS)


def get_fund_profile_csv_optional_columns() -> list[str]:
    return list(OPTIONAL_COLUMNS)


def load_fund_profiles_csv(path: str) -> pd.DataFrame:
    target = Path(path)
    if not target.exists():
        df = pd.DataFrame()
        df.attrs["warnings"] = [f"{path} 不存在。"]
        return df
    try:
        return pd.read_csv(target)
    except Exception as exc:  # noqa: BLE001 - keep UI resilient for damaged local CSV.
        df = pd.DataFrame()
        df.attrs["warnings"] = [f"{path} 读取失败：{exc}"]
        return df


def _clean_string(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def normalize_fund_profiles_csv(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    out = df.copy()
    out.columns = [str(column).strip().lower() for column in out.columns]
    for column in REQUIRED_COLUMNS + OPTIONAL_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA
    for column in [col for col in OUTPUT_COLUMNS if col != "exposure_weight"]:
        out[column] = out[column].map(_clean_string)
    raw_weight = out["exposure_weight"]
    numeric_weight = pd.to_numeric(raw_weight, errors="coerce")
    blank_weight = raw_weight.isna() | raw_weight.astype(str).str.strip().eq("")
    numeric_weight = numeric_weight.mask(blank_weight, 1.0)
    out["exposure_weight"] = numeric_weight
    return out[OUTPUT_COLUMNS].reset_index(drop=True)


def _taxonomy_theme_set(taxonomy: dict | None) -> set[str]:
    if taxonomy is None:
        taxonomy = load_theme_taxonomy()
    return set(get_theme_names(taxonomy))


def validate_fund_profiles_csv(
    df: pd.DataFrame,
    taxonomy: dict | None = None,
) -> dict:
    warnings: list[str] = []
    errors: list[str] = []
    if df is None or df.empty:
        return {
            "is_valid": False,
            "warning_count": 0,
            "error_count": 1,
            "warnings": [],
            "errors": ["无可用配置。"],
            "unknown_themes": [],
            "duplicated_profile_theme_count": 0,
            "invalid_weight_count": 0,
            "profile_count": 0,
            "row_count": 0,
            "validation_label": "无可用配置",
            "validation_reason": "CSV 不存在、为空或读取失败。",
        }
    normalized_columns = {str(column).strip().lower() for column in df.columns}
    missing_required = [column for column in REQUIRED_COLUMNS if column not in normalized_columns]
    for column in missing_required:
        errors.append(f"缺少必要字段：{column}。")
    normalized = normalize_fund_profiles_csv(df)
    if normalized.empty:
        errors.append("标准化后无可用配置行。")
    empty_profile_id = int(normalized["profile_id"].eq("").sum()) if "profile_id" in normalized else 0
    empty_profile_name = int(normalized["profile_name"].eq("").sum()) if "profile_name" in normalized else 0
    empty_theme_name = int(normalized["theme_name"].eq("").sum()) if "theme_name" in normalized else 0
    if empty_profile_id:
        warnings.append(f"{empty_profile_id} 行 profile_id 为空。")
    if empty_profile_name:
        warnings.append(f"{empty_profile_name} 行 profile_name 为空。")
    if empty_theme_name:
        warnings.append(f"{empty_theme_name} 行 theme_name 为空。")

    theme_names = _taxonomy_theme_set(taxonomy)
    themes = set(normalized["theme_name"].dropna().astype(str))
    unknown_themes = sorted(theme for theme in themes if theme and theme not in theme_names)
    if unknown_themes:
        warnings.append(f"存在未注册主题：{'，'.join(unknown_themes)}。")

    invalid_weight_mask = normalized["exposure_weight"].isna()
    invalid_weight_count = int(invalid_weight_mask.sum())
    if invalid_weight_count:
        errors.append(f"{invalid_weight_count} 行 exposure_weight 不是数字。")
    negative_count = int(normalized["exposure_weight"].lt(0).fillna(False).sum())
    if negative_count:
        errors.append(f"{negative_count} 行 exposure_weight 小于 0。")
    too_large_count = int(normalized["exposure_weight"].gt(1).fillna(False).sum())
    if too_large_count:
        warnings.append(f"{too_large_count} 行 exposure_weight 大于 1，请确认是否为比例。")

    duplicated_mask = normalized.duplicated(["profile_id", "theme_name"], keep=False) & normalized["profile_id"].ne("") & normalized["theme_name"].ne("")
    duplicated_count = int(duplicated_mask.sum())
    if duplicated_count:
        warnings.append(f"{duplicated_count} 行存在同一 profile_id 下重复 theme_name。")

    weight_sums = normalized.dropna(subset=["exposure_weight"]).groupby("profile_id", dropna=False)["exposure_weight"].sum()
    abnormal_profiles = [
        f"{profile_id or '<empty>'}={total:.2f}"
        for profile_id, total in weight_sums.items()
        if profile_id and (total < 0.8 or total > 1.2)
    ]
    if abnormal_profiles:
        warnings.append(f"以下 profile exposure_weight 总和偏离 1：{'，'.join(abnormal_profiles)}。")

    profile_count = int(normalized["profile_id"].replace("", pd.NA).dropna().nunique())
    row_count = int(len(normalized))
    if errors:
        label = "存在配置错误"
        reason = "CSV 存在必要字段缺失、非法权重或无可用配置，需要修正后再用于观察。"
    elif warnings:
        label = "存在轻微警告"
        reason = "CSV 可用于页面展示，但存在未注册主题、重复配置或权重提示，建议人工校准。"
    elif row_count:
        label = "配置可用"
        reason = "CSV 字段完整，主题名称与主题库匹配，权重未发现明显异常。"
    else:
        label = "无可用配置"
        reason = "CSV 无可用配置行。"
    return {
        "is_valid": not errors and row_count > 0,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
        "unknown_themes": unknown_themes,
        "duplicated_profile_theme_count": duplicated_count,
        "invalid_weight_count": invalid_weight_count + negative_count,
        "profile_count": profile_count,
        "row_count": row_count,
        "validation_label": label,
        "validation_reason": reason,
    }


def build_profile_summary_from_csv(
    df: pd.DataFrame,
    validation_report: dict | None = None,
) -> pd.DataFrame:
    normalized = normalize_fund_profiles_csv(df)
    if normalized.empty:
        return pd.DataFrame(
            columns=[
                "profile_id",
                "profile_name",
                "fund_code",
                "fund_type",
                "theme_count",
                "total_exposure_weight",
                "core_theme_count",
                "warning_count",
                "validation_label",
                "description",
            ]
        )
    report = validation_report or validate_fund_profiles_csv(normalized)
    rows = []
    for profile_id, group in normalized.groupby("profile_id", dropna=False):
        rows.append(
            {
                "profile_id": profile_id,
                "profile_name": group["profile_name"].replace("", pd.NA).dropna().iloc[0] if not group["profile_name"].replace("", pd.NA).dropna().empty else "--",
                "fund_code": group["fund_code"].replace("", pd.NA).dropna().iloc[0] if not group["fund_code"].replace("", pd.NA).dropna().empty else "--",
                "fund_type": group["fund_type"].replace("", pd.NA).dropna().iloc[0] if not group["fund_type"].replace("", pd.NA).dropna().empty else "--",
                "theme_count": int(group["theme_name"].replace("", pd.NA).dropna().nunique()),
                "total_exposure_weight": float(pd.to_numeric(group["exposure_weight"], errors="coerce").sum()),
                "core_theme_count": int(group["exposure_role"].str.lower().eq("core").sum()),
                "warning_count": int(report.get("warning_count", 0)),
                "validation_label": report.get("validation_label", "--"),
                "description": group["description"].replace("", pd.NA).dropna().iloc[0] if not group["description"].replace("", pd.NA).dropna().empty else "",
            }
        )
    return pd.DataFrame(rows).reset_index(drop=True)


def build_profile_theme_exposure_table(
    df: pd.DataFrame,
    taxonomy: dict | None = None,
) -> pd.DataFrame:
    normalized = normalize_fund_profiles_csv(df)
    if normalized.empty:
        return pd.DataFrame()
    taxonomy = taxonomy or load_theme_taxonomy()
    definition = build_theme_definition_table(taxonomy)
    group_map = {}
    if not definition.empty:
        group_map = dict(zip(definition["theme_name"], definition["theme_group"], strict=False))
    theme_names = _taxonomy_theme_set(taxonomy)
    out = normalized.copy()
    out["theme_group"] = out["theme_name"].map(group_map).fillna("--")
    out["taxonomy_registered"] = out["theme_name"].isin(theme_names)
    return out[
        [
            "profile_id",
            "profile_name",
            "fund_code",
            "fund_type",
            "theme_name",
            "theme_group",
            "exposure_weight",
            "exposure_role",
            "taxonomy_registered",
            "notes",
        ]
    ].reset_index(drop=True)


def _status_to_observation(status: str, registered: bool) -> tuple[float, str, str]:
    if not registered:
        return 0.0, "配置需检查", "该主题未注册在当前主题库中，需先校准主题名称。"
    if not status:
        return 0.0, "样本不足", "暂无主题雷达数据，当前仅展示配置关系。"
    score = float(STATUS_SCORE.get(status, 0))
    if status in {"强流入", "弱流入"}:
        return score, "关注主题资金偏强", "该主题当前资金状态偏强，仅用于主题观察。"
    if status in {"强流出", "弱流出"}:
        return score, "关注主题资金承压", "该主题当前资金状态承压，仅用于主题观察。"
    return score, "关注主题资金分化", "该主题当前资金状态分化，仅用于主题观察。"


def merge_profile_exposure_with_theme_radar(
    exposure_df: pd.DataFrame,
    radar_df: pd.DataFrame | None,
) -> pd.DataFrame:
    if exposure_df is None or exposure_df.empty:
        return pd.DataFrame()
    exposure = exposure_df.copy()
    if "taxonomy_registered" not in exposure.columns:
        exposure["taxonomy_registered"] = True
    if radar_df is None or radar_df.empty:
        radar = pd.DataFrame(columns=["theme_name"])
    else:
        radar = radar_df.copy()
        if "theme_name" not in radar.columns and "sector_name" in radar.columns:
            radar["theme_name"] = radar["sector_name"]
    radar_columns = ["theme_name", "main_net_inflow_billion", "theme_status", "match_strategy", "source_sector_count"]
    for column in radar_columns:
        if column not in radar.columns:
            radar[column] = pd.NA
    merged = exposure.merge(radar[radar_columns], on="theme_name", how="left")
    merged["source_count"] = pd.to_numeric(merged.get("source_sector_count"), errors="coerce").fillna(0).astype(int)
    merged["theme_status"] = merged["theme_status"].fillna("")
    scores = []
    labels = []
    reasons = []
    for _, row in merged.iterrows():
        score, label, reason = _status_to_observation(str(row.get("theme_status") or ""), bool(row.get("taxonomy_registered")))
        weight = float(row.get("exposure_weight") or 0)
        scores.append(weight * score)
        labels.append(label)
        reasons.append(reason)
    merged["weighted_theme_score"] = scores
    merged["observation_label"] = labels
    merged["observation_reason"] = reasons
    return merged[
        [
            "profile_id",
            "profile_name",
            "fund_code",
            "fund_type",
            "theme_name",
            "theme_group",
            "exposure_weight",
            "exposure_role",
            "taxonomy_registered",
            "main_net_inflow_billion",
            "theme_status",
            "match_strategy",
            "source_count",
            "weighted_theme_score",
            "observation_label",
            "observation_reason",
        ]
    ].reset_index(drop=True)


def _profile_label(score: float, unknown_count: int, matched_count: int) -> str:
    if unknown_count > 0:
        return "配置需检查"
    if matched_count <= 0:
        return "样本不足"
    if score >= 0.4:
        return "关注主题资金偏强"
    if score <= -0.4:
        return "关注主题资金承压"
    return "关注主题资金分化"


def summarize_profile_observations(
    merged_df: pd.DataFrame,
) -> pd.DataFrame:
    if merged_df is None or merged_df.empty:
        return pd.DataFrame()
    rows = []
    for profile_id, group in merged_df.groupby("profile_id", dropna=False):
        registered = group["taxonomy_registered"].fillna(False).astype(bool)
        statuses = group["theme_status"].fillna("")
        unknown_count = int((~registered).sum())
        positive_count = int(statuses.isin(["强流入", "弱流入"]).sum())
        pressure_count = int(statuses.isin(["强流出", "弱流出"]).sum())
        neutral_count = int(statuses.eq("分歧/中性").sum())
        matched_count = int(statuses.ne("").sum())
        total_weight = float(pd.to_numeric(group["exposure_weight"], errors="coerce").fillna(0).sum())
        score_sum = float(pd.to_numeric(group["weighted_theme_score"], errors="coerce").fillna(0).sum())
        score = score_sum / total_weight if total_weight else 0.0
        label = _profile_label(score, unknown_count, matched_count)
        name = group["profile_name"].replace("", pd.NA).dropna().iloc[0] if not group["profile_name"].replace("", pd.NA).dropna().empty else str(profile_id)
        if unknown_count > 0:
            reason = f"{name} 配置中存在未注册主题，请先检查主题名称；当前结果仅作配置校验参考。"
        elif matched_count <= 0:
            reason = f"{name} 暂无可匹配主题雷达数据，仅展示 CSV 主题暴露配置。"
        elif label == "关注主题资金偏强":
            reason = f"{name} 关联主题中偏强主题较多，当前主题资金观察偏强。"
        elif label == "关注主题资金承压":
            reason = f"{name} 关联主题中承压主题较多，当前主题资金观察承压。"
        else:
            reason = f"{name} 关联主题资金状态分化，适合继续观察主题结构。"
        rows.append(
            {
                "profile_id": profile_id,
                "profile_name": name,
                "fund_code": group["fund_code"].replace("", pd.NA).dropna().iloc[0] if not group["fund_code"].replace("", pd.NA).dropna().empty else "--",
                "fund_type": group["fund_type"].replace("", pd.NA).dropna().iloc[0] if not group["fund_type"].replace("", pd.NA).dropna().empty else "--",
                "related_theme_count": int(group["theme_name"].replace("", pd.NA).dropna().nunique()),
                "positive_theme_count": positive_count,
                "pressure_theme_count": pressure_count,
                "neutral_theme_count": neutral_count,
                "unknown_theme_count": unknown_count,
                "weighted_net_inflow_score": score,
                "profile_observation_label": label,
                "profile_observation_reason": reason,
            }
        )
    return pd.DataFrame(rows).sort_values("weighted_net_inflow_score", ascending=False).reset_index(drop=True)


def validate_profile_observation_text(text: str) -> list[str]:
    value = str(text or "")
    return [word for word in FORBIDDEN_PROFILE_TEXT if word in value]
