from __future__ import annotations

import pandas as pd

from src.theme_pool import build_theme_snapshot
from src.theme_radar import FORBIDDEN_ADVICE_WORDS


INDUSTRY_SECTOR_TYPE = "行业资金流"

HOTSPOT_LABELS = {
    "persistent_inflow": "持续流入主题",
    "improving": "日内改善主题",
    "reversal_to_inflow": "由弱转强主题",
    "persistent_outflow": "持续流出主题",
    "worsening": "日内走弱主题",
    "neutral_watch": "分化观察主题",
}

HOTSPOT_PRIORITY = {
    "reversal_to_inflow": 1,
    "persistent_inflow": 2,
    "improving": 3,
    "worsening": 4,
    "persistent_outflow": 5,
    "neutral_watch": 6,
}


def _clean_reason(reason: str) -> str:
    for word in FORBIDDEN_ADVICE_WORDS + ("推荐买", "建议买", "建仓", "清仓"):
        reason = reason.replace(word, "")
    return reason


def _industry_ticks(ticks_df: pd.DataFrame) -> pd.DataFrame:
    if ticks_df is None or ticks_df.empty:
        return pd.DataFrame()
    if "sector_type" not in ticks_df.columns:
        return ticks_df.copy()
    return ticks_df[ticks_df["sector_type"].eq(INDUSTRY_SECTOR_TYPE)].copy()


def build_theme_intraday_history(
    ticks_df: pd.DataFrame,
    mode: str = "breadth",
) -> pd.DataFrame:
    df = _industry_ticks(ticks_df)
    if df.empty or "captured_time" not in df.columns:
        return pd.DataFrame()
    if "captured_at" in df.columns:
        df["captured_at"] = pd.to_datetime(df["captured_at"], errors="coerce")
    rows = []
    warnings = []
    for captured_time, frame in df.groupby("captured_time", sort=True):
        try:
            snapshot = build_theme_snapshot(frame, theme_mode=mode)
        except Exception as exc:
            warnings.append(f"{captured_time}: 主题快照构建失败: {exc}")
            continue
        if snapshot.empty:
            warnings.append(f"{captured_time}: 主题快照为空")
            continue
        for _, row in snapshot.iterrows():
            rows.append(
                {
                    "captured_time": str(captured_time),
                    "theme_name": row.get("theme_name") or row.get("sector_name"),
                    "main_net_inflow_billion": row.get("main_net_inflow_billion"),
                    "theme_status": row.get("theme_status"),
                    "theme_status_level": row.get("theme_status_level"),
                    "match_strategy": row.get("match_strategy"),
                    "source_count": row.get("source_sector_count"),
                    "source_sectors": row.get("source_sectors"),
                    "mode": mode,
                }
            )
    if not rows:
        empty = pd.DataFrame()
        empty.attrs["warnings"] = warnings
        return empty
    out = pd.DataFrame(rows)
    out["main_net_inflow_billion"] = pd.to_numeric(out["main_net_inflow_billion"], errors="coerce")
    out = out.dropna(subset=["theme_name", "main_net_inflow_billion"]).reset_index(drop=True)
    out.attrs["warnings"] = warnings
    return out


def calculate_intraday_theme_metrics(
    theme_history_df: pd.DataFrame,
) -> pd.DataFrame:
    if theme_history_df is None or theme_history_df.empty:
        return pd.DataFrame()
    df = theme_history_df.copy()
    df["main_net_inflow_billion"] = pd.to_numeric(df["main_net_inflow_billion"], errors="coerce")
    df = df.dropna(subset=["captured_time", "theme_name", "main_net_inflow_billion"])
    if df.empty:
        return pd.DataFrame()
    df["_time_order"] = pd.factorize(df["captured_time"], sort=True)[0]
    df["rank"] = df.groupby("captured_time")["main_net_inflow_billion"].rank(method="min", ascending=False).astype(int)
    rows = []
    for theme_name, group in df.sort_values("_time_order").groupby("theme_name", sort=False):
        group = group.sort_values("_time_order")
        first = group.iloc[0]
        latest = group.iloc[-1]
        first_value = float(first["main_net_inflow_billion"])
        latest_value = float(latest["main_net_inflow_billion"])
        total = int(len(group))
        positive_count = int(group["main_net_inflow_billion"].gt(0).sum())
        negative_count = int(group["main_net_inflow_billion"].lt(0).sum())
        rows.append(
            {
                "theme_name": theme_name,
                "first_value": first_value,
                "latest_value": latest_value,
                "max_value": float(group["main_net_inflow_billion"].max()),
                "min_value": float(group["main_net_inflow_billion"].min()),
                "value_change": latest_value - first_value,
                "abs_value_change": abs(latest_value - first_value),
                "first_rank": int(first["rank"]),
                "latest_rank": int(latest["rank"]),
                "rank_change": int(first["rank"] - latest["rank"]),
                "latest_status": latest.get("theme_status"),
                "latest_status_level": latest.get("theme_status_level"),
                "positive_time_count": positive_count,
                "negative_time_count": negative_count,
                "total_time_count": total,
                "positive_ratio": positive_count / total if total else 0,
                "negative_ratio": negative_count / total if total else 0,
                "latest_match_strategy": latest.get("match_strategy"),
                "latest_source_count": int(latest.get("source_count") or 0),
                "latest_source_sectors": latest.get("source_sectors"),
            }
        )
    return pd.DataFrame(rows).reset_index(drop=True)


def classify_intraday_hotspot(row: pd.Series) -> tuple[str, str]:
    latest_value = float(row.get("latest_value", 0) or 0)
    first_value = float(row.get("first_value", 0) or 0)
    value_change = float(row.get("value_change", 0) or 0)
    rank_change = float(row.get("rank_change", 0) or 0)
    positive_ratio = float(row.get("positive_ratio", 0) or 0)
    negative_ratio = float(row.get("negative_ratio", 0) or 0)
    if latest_value >= 30 and positive_ratio >= 0.6:
        return "persistent_inflow", "日内多数时间保持净流入，当前资金仍偏强。"
    if value_change >= 30 or rank_change >= 3:
        return "improving", "日内资金状态较早盘改善，排名明显上升。"
    if first_value < 0 and latest_value > 5:
        return "reversal_to_inflow", "早盘净流出后转为净流入，资金方向出现修复。"
    if latest_value <= -30 and negative_ratio >= 0.6:
        return "persistent_outflow", "日内多数时间保持净流出，当前资金承压。"
    if value_change <= -30 or rank_change <= -3:
        return "worsening", "日内资金状态较早盘走弱，排名明显回落。"
    return "neutral_watch", "日内资金状态分化，暂以观察为主。"


def build_intraday_hotspot_pool(
    theme_metrics_df: pd.DataFrame,
    top_n: int = 12,
) -> pd.DataFrame:
    if theme_metrics_df is None or theme_metrics_df.empty:
        return pd.DataFrame()
    df = theme_metrics_df.copy()
    classifications = df.apply(classify_intraday_hotspot, axis=1)
    df["hotspot_type"] = [item[0] for item in classifications]
    df["hotspot_reason"] = [_clean_reason(item[1]) for item in classifications]
    df["hotspot_label"] = df["hotspot_type"].map(HOTSPOT_LABELS).fillna("分化观察主题")
    df["display_priority"] = df["hotspot_type"].map(HOTSPOT_PRIORITY).fillna(99).astype(int)
    return (
        df.sort_values(
            ["display_priority", "abs_value_change", "latest_value"],
            ascending=[True, False, False],
        )
        .head(top_n)
        .reset_index(drop=True)
    )


def split_hotspot_sections(
    hotspot_pool_df: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    if hotspot_pool_df is None or hotspot_pool_df.empty:
        empty = pd.DataFrame()
        return {
            "positive_hotspots": empty,
            "improving_hotspots": empty,
            "pressure_hotspots": empty,
            "neutral_hotspots": empty,
        }
    df = hotspot_pool_df.copy()
    return {
        "positive_hotspots": df[df["hotspot_type"].isin(["persistent_inflow", "reversal_to_inflow"])],
        "improving_hotspots": df[df["hotspot_type"].eq("improving")],
        "pressure_hotspots": df[df["hotspot_type"].isin(["persistent_outflow", "worsening"])],
        "neutral_hotspots": df[df["hotspot_type"].eq("neutral_watch")],
    }


def build_intraday_hotspot_summary(
    hotspot_pool_df: pd.DataFrame,
) -> dict:
    if hotspot_pool_df is None or hotspot_pool_df.empty:
        return {
            "total_themes": 0,
            "positive_hotspot_count": 0,
            "improving_count": 0,
            "pressure_count": 0,
            "neutral_count": 0,
            "strongest_theme": None,
            "weakest_theme": None,
            "biggest_improving_theme": None,
            "biggest_worsening_theme": None,
            "summary_label": "日内热点分化",
            "summary_reason": "当前暂无足够主题快照，等待更多日内资金流数据。",
        }
    sections = split_hotspot_sections(hotspot_pool_df)
    positive_count = int(len(sections["positive_hotspots"]))
    improving_count = int(len(sections["improving_hotspots"]))
    pressure_count = int(len(sections["pressure_hotspots"]))
    neutral_count = int(len(sections["neutral_hotspots"]))
    if positive_count >= pressure_count + 2:
        label = "日内热点偏活跃"
        reason = "当前日内热点中流入或修复主题更多，资金短线活跃度较高。"
    elif pressure_count >= positive_count + 2:
        label = "日内热点偏承压"
        reason = "当前日内热点中承压主题数量更多，说明资金短线更偏谨慎。"
    else:
        label = "日内热点分化"
        reason = "当前日内热点中流入和流出主题并存，主题结构分化较明显。"
    strongest = hotspot_pool_df.sort_values("latest_value", ascending=False).iloc[0]
    weakest = hotspot_pool_df.sort_values("latest_value", ascending=True).iloc[0]
    improving = hotspot_pool_df.sort_values("value_change", ascending=False).iloc[0]
    worsening = hotspot_pool_df.sort_values("value_change", ascending=True).iloc[0]
    return {
        "total_themes": int(len(hotspot_pool_df)),
        "positive_hotspot_count": positive_count,
        "improving_count": improving_count,
        "pressure_count": pressure_count,
        "neutral_count": neutral_count,
        "strongest_theme": strongest.get("theme_name"),
        "weakest_theme": weakest.get("theme_name"),
        "biggest_improving_theme": improving.get("theme_name"),
        "biggest_worsening_theme": worsening.get("theme_name"),
        "summary_label": label,
        "summary_reason": _clean_reason(reason),
    }
