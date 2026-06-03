from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.theme_radar import FORBIDDEN_ADVICE_WORDS, STATUS_SCORE


DEFAULT_FUND_PROFILE = {
    "profile_name": "默认基金关注组合",
    "description": "本配置仅用于本地主题观察示例，不代表真实持仓。",
    "funds": [
        {
            "fund_name": "半导体主题基金示例",
            "fund_code": "DEMO-SEMI",
            "fund_type": "主题基金",
            "themes": [
                {"theme_name": "半导体/芯片链", "weight": 0.75},
                {"theme_name": "AI算力/TMT", "weight": 0.15},
                {"theme_name": "新能源链", "weight": 0.10},
            ],
        },
        {
            "fund_name": "AI 科技主题基金示例",
            "fund_code": "DEMO-AI",
            "fund_type": "主题基金",
            "themes": [
                {"theme_name": "AI算力/TMT", "weight": 0.65},
                {"theme_name": "半导体/芯片链", "weight": 0.20},
                {"theme_name": "证券金融", "weight": 0.15},
            ],
        },
        {
            "fund_name": "新能源主题基金示例",
            "fund_code": "DEMO-NEWENERGY",
            "fund_type": "主题基金",
            "themes": [
                {"theme_name": "新能源链", "weight": 0.80},
                {"theme_name": "半导体/芯片链", "weight": 0.10},
                {"theme_name": "红利防御", "weight": 0.10},
            ],
        },
        {
            "fund_name": "红利防御主题基金示例",
            "fund_code": "DEMO-DIVIDEND",
            "fund_type": "主题基金",
            "themes": [
                {"theme_name": "红利防御", "weight": 0.85},
                {"theme_name": "证券金融", "weight": 0.10},
                {"theme_name": "消费", "weight": 0.05},
            ],
        },
    ],
}


def load_fund_profiles(path: str = "config/fund_profiles.json") -> dict:
    profile_path = Path(path)
    if not profile_path.exists():
        profile = DEFAULT_FUND_PROFILE.copy()
        profile["_load_warning"] = f"{path} 不存在，已使用默认基金主题配置。"
        return profile
    try:
        with profile_path.open("r", encoding="utf-8") as file:
            profile = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        profile = DEFAULT_FUND_PROFILE.copy()
        profile["_load_warning"] = f"{path} 读取失败，已使用默认基金主题配置：{exc}"
        return profile
    if not isinstance(profile, dict):
        profile = DEFAULT_FUND_PROFILE.copy()
        profile["_load_warning"] = f"{path} 格式不是 JSON object，已使用默认基金主题配置。"
    return profile


def get_funds(profile: dict) -> list[dict]:
    funds = profile.get("funds", []) if isinstance(profile, dict) else []
    return funds if isinstance(funds, list) else []


def _safe_weight(value) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_fund_profile(profile: dict) -> list[str]:
    warnings = []
    funds = get_funds(profile)
    if not funds:
        return ["funds 不存在或为空。"]
    for idx, fund in enumerate(funds, start=1):
        fund_name = fund.get("fund_name") or f"第 {idx} 只基金"
        for field in ("fund_name", "fund_code", "themes"):
            if field not in fund or fund.get(field) in (None, ""):
                warnings.append(f"{fund_name}: 缺少 {field}。")
        themes = fund.get("themes", [])
        if not isinstance(themes, list) or not themes:
            warnings.append(f"{fund_name}: themes 不存在或为空。")
            continue
        weights = []
        for theme_idx, item in enumerate(themes, start=1):
            if not isinstance(item, dict):
                warnings.append(f"{fund_name}: 第 {theme_idx} 个 theme 配置不是 object。")
                continue
            if not item.get("theme_name"):
                warnings.append(f"{fund_name}: 第 {theme_idx} 个 theme 缺少 theme_name。")
            weight = _safe_weight(item.get("weight"))
            if weight is None:
                warnings.append(f"{fund_name}: {item.get('theme_name', theme_idx)} weight 不是数字。")
            else:
                weights.append(weight)
        if weights and abs(sum(weights) - 1.0) > 0.02:
            warnings.append(f"{fund_name}: theme weight 总和为 {sum(weights):.2f}，计算时会归一化。")
    load_warning = profile.get("_load_warning") if isinstance(profile, dict) else None
    if load_warning:
        warnings.insert(0, str(load_warning))
    return warnings


def normalize_fund_theme_weights(fund: dict) -> dict:
    normalized = {key: value for key, value in fund.items() if key != "themes"}
    themes = []
    valid_items = []
    total = 0.0
    for item in fund.get("themes", []):
        if not isinstance(item, dict):
            continue
        weight = _safe_weight(item.get("weight"))
        if weight is None:
            weight = 0.0
        total += weight
        valid_items.append((item, weight))
    for item, weight in valid_items:
        themes.append(
            {
                "theme_name": item.get("theme_name"),
                "weight": weight,
                "normalized_weight": weight / total if total else 0.0,
            }
        )
    normalized["themes"] = themes
    return normalized


def build_fund_theme_exposure(funds: list[dict]) -> pd.DataFrame:
    rows = []
    for fund in funds:
        normalized = normalize_fund_theme_weights(fund)
        for item in normalized.get("themes", []):
            if not item.get("theme_name"):
                continue
            rows.append(
                {
                    "fund_name": fund.get("fund_name", "--"),
                    "fund_code": fund.get("fund_code", "--"),
                    "fund_type": fund.get("fund_type", "--"),
                    "theme_name": item.get("theme_name"),
                    "raw_weight": item.get("weight", 0.0),
                    "normalized_weight": item.get("normalized_weight", 0.0),
                }
            )
    return pd.DataFrame(
        rows,
        columns=["fund_name", "fund_code", "fund_type", "theme_name", "raw_weight", "normalized_weight"],
    )


def status_to_score(status: str) -> int:
    return int(STATUS_SCORE.get(status, 0))


def _impact_label(score: float) -> str:
    if score >= 1.0:
        return "相关主题资金偏强"
    if 0.2 <= score < 1.0:
        return "相关主题小幅偏强"
    if -0.2 < score < 0.2:
        return "相关主题分歧/中性"
    if -1.0 < score <= -0.2:
        return "相关主题小幅承压"
    return "相关主题明显承压"


def _fund_label(score: float) -> str:
    if score >= 1.0:
        return "关注组合相关主题资金偏强"
    if 0.2 <= score < 1.0:
        return "关注组合相关主题略偏强"
    if -0.2 < score < 0.2:
        return "关注组合相关主题分化"
    if -1.0 < score <= -0.2:
        return "关注组合相关主题略承压"
    return "关注组合相关主题明显承压"


def _clean_reason(reason: str) -> str:
    for word in FORBIDDEN_ADVICE_WORDS + ("推荐买", "建议买", "建仓", "清仓"):
        reason = reason.replace(word, "")
    return reason


def _impact_reason(row: pd.Series) -> str:
    fund = row.get("fund_name", "该关注基金")
    theme = row.get("theme_name", "相关主题")
    weight = float(row.get("normalized_weight", 0) or 0)
    status = row.get("theme_status", "分歧/中性")
    if status in {"强流入", "弱流入"}:
        reason = f"{fund} 配置的 {theme} 权重约 {weight:.0%}，当前主题资金偏强。"
    elif status in {"强流出", "弱流出"}:
        reason = f"{fund} 配置的 {theme} 权重约 {weight:.0%}，当前相关主题资金承压。"
    else:
        reason = f"{fund} 配置的 {theme} 权重约 {weight:.0%}，当前相关主题资金状态分化。"
    return _clean_reason(reason)


def build_holding_related_pool(
    exposure_df: pd.DataFrame,
    theme_radar_df: pd.DataFrame,
) -> pd.DataFrame:
    if exposure_df is None or exposure_df.empty:
        return pd.DataFrame()
    if theme_radar_df is None or theme_radar_df.empty:
        radar = pd.DataFrame(columns=["theme_name"])
    else:
        radar = theme_radar_df.copy()
        if "theme_name" not in radar.columns and "sector_name" in radar.columns:
            radar["theme_name"] = radar["sector_name"]
    columns = [
        "theme_name",
        "main_net_inflow_billion",
        "theme_status",
        "theme_status_level",
        "radar_label",
        "radar_reason",
        "theme_value_label",
        "match_strategy",
    ]
    for column in columns:
        if column not in radar.columns:
            radar[column] = pd.NA
    merged = exposure_df.merge(radar[columns], on="theme_name", how="left")
    merged["theme_status"] = merged["theme_status"].fillna("分歧/中性")
    merged["theme_score"] = merged["theme_status"].map(status_to_score).fillna(0)
    merged["holding_impact_score"] = merged["normalized_weight"].astype(float) * merged["theme_score"].astype(float)
    merged["holding_impact_label"] = merged["holding_impact_score"].map(_impact_label)
    merged["holding_impact_reason"] = merged.apply(_impact_reason, axis=1)
    return merged[
        [
            "fund_name",
            "fund_code",
            "fund_type",
            "theme_name",
            "normalized_weight",
            "main_net_inflow_billion",
            "theme_status",
            "theme_status_level",
            "radar_label",
            "radar_reason",
            "theme_value_label",
            "match_strategy",
            "holding_impact_score",
            "holding_impact_label",
            "holding_impact_reason",
        ]
    ].reset_index(drop=True)


def _join_top_themes(df: pd.DataFrame, positive: bool) -> str:
    if df.empty:
        return ""
    work = df[df["holding_impact_score"].gt(0)] if positive else df[df["holding_impact_score"].lt(0)]
    if work.empty:
        return ""
    work = work.sort_values("holding_impact_score", ascending=not positive)
    return "，".join(work["theme_name"].head(3).astype(str).tolist())


def _summary_reason(row: pd.Series) -> str:
    fund = row.get("fund_name", "该关注基金")
    label = row.get("fund_impact_label", "关注组合相关主题分化")
    pos = row.get("top_positive_themes") or "暂无明显偏强主题"
    neg = row.get("top_negative_themes") or "暂无明显承压主题"
    reason = f"{fund}：{label}。偏强主题：{pos}；承压主题：{neg}。这是主题资金观察，不代表真实持仓或净值预测。"
    return _clean_reason(reason)


def build_fund_summary(holding_pool_df: pd.DataFrame) -> pd.DataFrame:
    if holding_pool_df is None or holding_pool_df.empty:
        return pd.DataFrame()
    rows = []
    for (fund_name, fund_code, fund_type), group in holding_pool_df.groupby(["fund_name", "fund_code", "fund_type"], dropna=False):
        score = float(group["holding_impact_score"].sum())
        row = {
            "fund_name": fund_name,
            "fund_code": fund_code,
            "fund_type": fund_type,
            "weighted_impact_score": score,
            "fund_impact_label": _fund_label(score),
            "top_negative_themes": _join_top_themes(group, positive=False),
            "top_positive_themes": _join_top_themes(group, positive=True),
        }
        row["summary_reason"] = _summary_reason(pd.Series(row))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("weighted_impact_score", ascending=False).reset_index(drop=True)
