from __future__ import annotations

import pandas as pd


FORBIDDEN_ADVICE_WORDS = ("买入", "卖出", "加仓", "减仓", "抄底", "逃顶")

RADAR_LABELS = {
    "强流入": "资金强流入",
    "弱流入": "资金小幅流入",
    "分歧/中性": "资金分歧",
    "弱流出": "资金小幅流出",
    "强流出": "资金明显流出",
}

RADAR_PRIORITY = {
    "强流入": 90,
    "弱流入": 70,
    "分歧/中性": 50,
    "弱流出": 60,
    "强流出": 85,
}

STATUS_SCORE = {
    "强流入": 2,
    "弱流入": 1,
    "分歧/中性": 0,
    "弱流出": -1,
    "强流出": -2,
}


def _safe_float(value) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _radar_reason(row: pd.Series) -> str:
    theme = str(row.get("theme_name") or row.get("sector_name") or "该主题")
    status = str(row.get("theme_status") or "分歧/中性")
    label = str(row.get("theme_value_label") or "当前口径")
    if status == "强流入":
        reason = f"{theme}：{label}下主力净流入较强，当前主题资金偏活跃。"
    elif status == "弱流入":
        reason = f"{theme}：{label}下主力净流入为正，当前主题资金略偏强。"
    elif status == "强流出":
        reason = f"{theme}：{label}下主力净流出较大，短线资金承压。"
    elif status == "弱流出":
        reason = f"{theme}：{label}下主力净流出为负，资金表现偏谨慎。"
    else:
        reason = f"{theme}：{label}下资金方向不突出，主题内部可能存在分化。"
    for word in FORBIDDEN_ADVICE_WORDS:
        reason = reason.replace(word, "")
    return reason


def build_theme_radar_snapshot(theme_df: pd.DataFrame) -> pd.DataFrame:
    if theme_df is None or theme_df.empty:
        return pd.DataFrame()
    df = theme_df.copy()
    if "theme_name" not in df.columns:
        df["theme_name"] = df.get("sector_name")
    df["radar_label"] = df["theme_status"].map(RADAR_LABELS).fillna("资金分歧")
    df["radar_reason"] = df.apply(_radar_reason, axis=1)
    df["radar_priority"] = df["theme_status"].map(RADAR_PRIORITY).fillna(50).astype(int)
    return df.sort_values(["radar_priority", "main_net_inflow_billion"], ascending=[False, False]).reset_index(drop=True)


def build_market_temperature(theme_df: pd.DataFrame) -> dict:
    if theme_df is None or theme_df.empty:
        return {
            "total_themes": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "strong_inflow_count": 0,
            "strong_outflow_count": 0,
            "net_theme_score": 0,
            "market_temperature_label": "主题资金分化",
            "market_temperature_reason": "当前暂无可用主题快照，等待更多真实资金流数据。",
        }
    statuses = theme_df["theme_status"].fillna("分歧/中性")
    score = int(sum(STATUS_SCORE.get(status, 0) for status in statuses))
    positive_count = int(statuses.isin(["强流入", "弱流入"]).sum())
    negative_count = int(statuses.isin(["强流出", "弱流出"]).sum())
    neutral_count = int(statuses.eq("分歧/中性").sum())
    strong_inflow_count = int(statuses.eq("强流入").sum())
    strong_outflow_count = int(statuses.eq("强流出").sum())
    if score >= 4:
        label = "主题资金偏热"
    elif 1 <= score < 4:
        label = "主题资金略偏暖"
    elif -1 <= score <= 0:
        label = "主题资金分化"
    elif -4 < score < -1:
        label = "主题资金偏冷"
    else:
        label = "主题资金明显偏冷"

    if strong_inflow_count > strong_outflow_count:
        reason = "当前强流入主题多于强流出主题，主题资金偏活跃。"
    elif negative_count > positive_count:
        reason = "当前核心主题中，流出主题数量较多，资金情绪偏谨慎。"
    elif positive_count > negative_count:
        reason = "当前流入主题数量略多，资金温度略偏暖。"
    else:
        reason = "当前流入与流出主题接近，主题资金呈分化状态。"
    return {
        "total_themes": int(len(theme_df)),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "strong_inflow_count": strong_inflow_count,
        "strong_outflow_count": strong_outflow_count,
        "net_theme_score": score,
        "market_temperature_label": label,
        "market_temperature_reason": reason,
    }


def _value_sign(value: float) -> str:
    if value > 0:
        return "inflow"
    if value < 0:
        return "outflow"
    return "neutral"


def _status_from_value(value: float) -> str:
    if value >= 30:
        return "强流入"
    if 5 <= value < 30:
        return "弱流入"
    if -5 < value < 5:
        return "分歧/中性"
    if -30 < value <= -5:
        return "弱流出"
    return "强流出"


def _divergence_reason(theme: str, divergence_type: str) -> str:
    if divergence_type == "both_inflow":
        return f"{theme}：核心板块和相关板块均呈流入，主题资金共振较强。"
    if divergence_type == "both_outflow":
        return f"{theme}：核心板块和相关板块均呈流出，主题短线承压。"
    if divergence_type == "core_inflow_breadth_outflow":
        return f"{theme}：核心板块流入但相关板块偏流出，主题内部存在分化。"
    if divergence_type == "core_outflow_breadth_inflow":
        return f"{theme}：核心板块流出但相关板块仍有流入，主题内部存在分化。"
    return f"{theme}：核心与广度资金方向不够一致，适合继续观察资金结构。"


def compare_strict_and_breadth(strict_df: pd.DataFrame, breadth_df: pd.DataFrame) -> pd.DataFrame:
    if strict_df is None or strict_df.empty or breadth_df is None or breadth_df.empty:
        return pd.DataFrame()
    strict = strict_df.copy()
    breadth = breadth_df.copy()
    strict_name = "theme_name" if "theme_name" in strict.columns else "sector_name"
    breadth_name = "theme_name" if "theme_name" in breadth.columns else "sector_name"
    merged = strict[[strict_name, "main_net_inflow_billion", "theme_status"]].merge(
        breadth[[breadth_name, "main_net_inflow_billion", "theme_status"]],
        left_on=strict_name,
        right_on=breadth_name,
        suffixes=("_strict", "_breadth"),
    )
    rows = []
    for _, row in merged.iterrows():
        theme = row[strict_name]
        strict_value = _safe_float(row["main_net_inflow_billion_strict"])
        breadth_value = _safe_float(row["main_net_inflow_billion_breadth"])
        strict_sign = _value_sign(strict_value)
        breadth_sign = _value_sign(breadth_value)
        if strict_sign == "inflow" and breadth_sign == "inflow":
            divergence_type = "both_inflow"
        elif strict_sign == "outflow" and breadth_sign == "outflow":
            divergence_type = "both_outflow"
        elif strict_sign == "inflow" and breadth_sign == "outflow":
            divergence_type = "core_inflow_breadth_outflow"
        elif strict_sign == "outflow" and breadth_sign == "inflow":
            divergence_type = "core_outflow_breadth_inflow"
        else:
            divergence_type = "mixed_neutral"
        rows.append(
            {
                "theme_name": theme,
                "strict_value": strict_value,
                "breadth_value": breadth_value,
                "strict_status": row.get("theme_status_strict") or _status_from_value(strict_value),
                "breadth_status": row.get("theme_status_breadth") or _status_from_value(breadth_value),
                "divergence_type": divergence_type,
                "divergence_reason": _divergence_reason(theme, divergence_type),
                "priority": abs(strict_value - breadth_value),
            }
        )
    return pd.DataFrame(rows).sort_values("priority", ascending=False).drop(columns=["priority"]).reset_index(drop=True)

