from __future__ import annotations

import pandas as pd

from src.snapshot_catalog import load_snapshot_by_date
from src.theme_pool import build_theme_snapshot
from src.theme_radar import FORBIDDEN_ADVICE_WORDS


INDUSTRY_SECTOR_TYPE = "行业资金流"

TREND_LABELS = {
    "persistent_strength": "多日偏强主题",
    "improving_trend": "多日改善主题",
    "reversal_to_strength": "由弱转强主题",
    "persistent_pressure": "多日承压主题",
    "weakening_trend": "多日走弱主题",
    "mixed_trend": "多日分化主题",
}

TREND_PRIORITY = {
    "reversal_to_strength": 1,
    "persistent_strength": 2,
    "improving_trend": 3,
    "weakening_trend": 4,
    "persistent_pressure": 5,
    "mixed_trend": 6,
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


def _latest_frame_for_date(industry_df: pd.DataFrame) -> pd.DataFrame:
    if industry_df.empty:
        return pd.DataFrame()
    df = industry_df.copy()
    if "captured_at" in df.columns:
        df["captured_at"] = pd.to_datetime(df["captured_at"], errors="coerce")
        valid = df.dropna(subset=["captured_at"])
        if not valid.empty:
            latest_at = valid["captured_at"].max()
            return valid[valid["captured_at"].eq(latest_at)].copy()
    if "captured_time" not in df.columns:
        return df.copy()
    latest_time = df["captured_time"].dropna().astype(str).max()
    return df[df["captured_time"].astype(str).eq(str(latest_time))].copy()


def build_daily_theme_snapshots(
    catalog_df: pd.DataFrame,
    data_dir: str = "data/ticks",
    mode: str = "strict_representative",
) -> pd.DataFrame:
    if catalog_df is None or catalog_df.empty:
        empty = pd.DataFrame()
        empty.attrs["warnings"] = []
        return empty
    rows = []
    warnings = []
    catalog = catalog_df.copy()
    if "snapshot_date" not in catalog.columns:
        empty = pd.DataFrame()
        empty.attrs["warnings"] = ["snapshot_catalog 缺少 snapshot_date 字段"]
        return empty
    if "is_readable" in catalog.columns:
        catalog = catalog[catalog["is_readable"].fillna(False)]
    catalog = catalog.sort_values("snapshot_date")
    for _, catalog_row in catalog.iterrows():
        snapshot_date = str(catalog_row.get("snapshot_date") or "")
        if not snapshot_date:
            continue
        try:
            ticks = load_snapshot_by_date(snapshot_date, data_dir=data_dir)
            industry = _industry_ticks(ticks)
            latest = _latest_frame_for_date(industry)
            if latest.empty:
                warnings.append(f"{snapshot_date}: 缺少行业资金流最新快照")
                continue
            theme_snapshot = build_theme_snapshot(latest, theme_mode=mode)
        except Exception as exc:
            warnings.append(f"{snapshot_date}: 多日主题快照构建失败: {exc}")
            continue
        if theme_snapshot.empty:
            warnings.append(f"{snapshot_date}: 主题快照为空")
            continue
        captured_time = (
            str(latest["captured_time"].dropna().iloc[0])
            if "captured_time" in latest.columns and not latest["captured_time"].dropna().empty
            else None
        )
        for _, row in theme_snapshot.iterrows():
            rows.append(
                {
                    "snapshot_date": snapshot_date,
                    "captured_time": captured_time,
                    "theme_name": row.get("theme_name") or row.get("sector_name"),
                    "main_net_inflow_billion": row.get("main_net_inflow_billion"),
                    "theme_status": row.get("theme_status"),
                    "theme_status_level": row.get("theme_status_level"),
                    "match_strategy": row.get("match_strategy"),
                    "source_count": row.get("source_sector_count"),
                    "source_sectors": row.get("source_sectors"),
                    "mode": mode,
                    "quality_label": catalog_row.get("quality_label"),
                }
            )
    if not rows:
        empty = pd.DataFrame()
        empty.attrs["warnings"] = warnings
        return empty
    out = pd.DataFrame(rows)
    out["main_net_inflow_billion"] = pd.to_numeric(out["main_net_inflow_billion"], errors="coerce")
    out = out.dropna(subset=["snapshot_date", "theme_name", "main_net_inflow_billion"]).reset_index(drop=True)
    out.attrs["warnings"] = warnings
    return out


def calculate_multi_day_theme_metrics(
    daily_theme_df: pd.DataFrame,
) -> pd.DataFrame:
    if daily_theme_df is None or daily_theme_df.empty:
        return pd.DataFrame()
    df = daily_theme_df.copy()
    df["main_net_inflow_billion"] = pd.to_numeric(df["main_net_inflow_billion"], errors="coerce")
    df = df.dropna(subset=["snapshot_date", "theme_name", "main_net_inflow_billion"])
    if df.empty:
        return pd.DataFrame()
    df = df.sort_values(["snapshot_date", "theme_name"])
    rows = []
    for theme_name, group in df.groupby("theme_name", sort=False):
        group = group.sort_values("snapshot_date")
        first = group.iloc[0]
        latest = group.iloc[-1]
        first_value = float(first["main_net_inflow_billion"])
        latest_value = float(latest["main_net_inflow_billion"])
        total = int(group["snapshot_date"].nunique())
        positive_count = int(group["main_net_inflow_billion"].gt(5).sum())
        negative_count = int(group["main_net_inflow_billion"].lt(-5).sum())
        neutral_count = int(total - positive_count - negative_count)
        rows.append(
            {
                "theme_name": theme_name,
                "date_count": total,
                "first_date": str(first["snapshot_date"]),
                "latest_date": str(latest["snapshot_date"]),
                "first_value": first_value,
                "latest_value": latest_value,
                "max_value": float(group["main_net_inflow_billion"].max()),
                "min_value": float(group["main_net_inflow_billion"].min()),
                "value_change": latest_value - first_value,
                "abs_value_change": abs(latest_value - first_value),
                "positive_day_count": positive_count,
                "negative_day_count": negative_count,
                "neutral_day_count": neutral_count,
                "positive_ratio": positive_count / total if total else 0,
                "negative_ratio": negative_count / total if total else 0,
                "latest_status": latest.get("theme_status"),
                "latest_status_level": latest.get("theme_status_level"),
                "latest_match_strategy": latest.get("match_strategy"),
                "latest_source_count": int(latest.get("source_count") or 0),
                "latest_source_sectors": latest.get("source_sectors"),
            }
        )
    return pd.DataFrame(rows).reset_index(drop=True)


def classify_multi_day_trend(row: pd.Series) -> tuple[str, str]:
    latest_value = float(row.get("latest_value", 0) or 0)
    first_value = float(row.get("first_value", 0) or 0)
    value_change = float(row.get("value_change", 0) or 0)
    positive_ratio = float(row.get("positive_ratio", 0) or 0)
    negative_ratio = float(row.get("negative_ratio", 0) or 0)
    if latest_value >= 30 and positive_ratio >= 0.6:
        return "persistent_strength", "多个缓存日期中该主题多次保持净流入，最近一次仍偏强。"
    if value_change >= 30:
        return "improving_trend", "相比最早缓存日期，最近一次主题资金状态明显改善。"
    if first_value < 0 and latest_value > 5:
        return "reversal_to_strength", "该主题从早期净流出转为最近净流入，历史缓存中出现修复。"
    if latest_value <= -30 and negative_ratio >= 0.6:
        return "persistent_pressure", "多个缓存日期中该主题多次保持净流出，最近一次仍承压。"
    if value_change <= -30:
        return "weakening_trend", "相比最早缓存日期，最近一次主题资金状态明显走弱。"
    return "mixed_trend", "多个缓存日期中的主题资金状态分化，暂以观察为主。"


def build_multi_day_trend_pool(
    metrics_df: pd.DataFrame,
    top_n: int = 12,
) -> pd.DataFrame:
    if metrics_df is None or metrics_df.empty:
        return pd.DataFrame()
    df = metrics_df.copy()
    classifications = df.apply(classify_multi_day_trend, axis=1)
    df["trend_type"] = [item[0] for item in classifications]
    df["trend_reason"] = [_clean_reason(item[1]) for item in classifications]
    df["trend_label"] = df["trend_type"].map(TREND_LABELS).fillna("多日分化主题")
    df["display_priority"] = df["trend_type"].map(TREND_PRIORITY).fillna(99).astype(int)
    return (
        df.sort_values(
            ["display_priority", "abs_value_change", "latest_value"],
            ascending=[True, False, False],
        )
        .head(top_n)
        .reset_index(drop=True)
    )


def split_multi_day_trend_sections(
    trend_pool_df: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    if trend_pool_df is None or trend_pool_df.empty:
        empty = pd.DataFrame()
        return {
            "strength_trends": empty,
            "improving_trends": empty,
            "pressure_trends": empty,
            "mixed_trends": empty,
        }
    df = trend_pool_df.copy()
    return {
        "strength_trends": df[df["trend_type"].isin(["persistent_strength", "reversal_to_strength"])],
        "improving_trends": df[df["trend_type"].eq("improving_trend")],
        "pressure_trends": df[df["trend_type"].isin(["persistent_pressure", "weakening_trend"])],
        "mixed_trends": df[df["trend_type"].eq("mixed_trend")],
    }


def build_multi_day_trend_summary(
    trend_pool_df: pd.DataFrame,
) -> dict:
    if trend_pool_df is None or trend_pool_df.empty:
        return {
            "total_themes": 0,
            "date_count": 0,
            "strength_count": 0,
            "improving_count": 0,
            "pressure_count": 0,
            "mixed_count": 0,
            "strongest_theme": None,
            "weakest_theme": None,
            "biggest_improving_theme": None,
            "biggest_weakening_theme": None,
            "summary_label": "多日主题结构分化",
            "summary_reason": "当前本地缓存日期不足，暂无法判断多日主题趋势。",
        }
    sections = split_multi_day_trend_sections(trend_pool_df)
    strength_count = int(len(sections["strength_trends"]))
    improving_count = int(len(sections["improving_trends"]))
    pressure_count = int(len(sections["pressure_trends"]))
    mixed_count = int(len(sections["mixed_trends"]))
    if strength_count >= pressure_count + 2:
        label = "多日主题结构偏强"
        reason = "当前本地缓存日期中，偏强或修复主题数量更多，历史样本内资金活跃度较高。"
    elif pressure_count >= strength_count + 2:
        label = "多日主题结构偏弱"
        reason = "当前本地缓存日期中，承压主题数量更多，说明历史样本内资金更偏谨慎。"
    else:
        label = "多日主题结构分化"
        reason = "当前本地缓存日期中，流入和流出主题并存，主题结构分化明显。"
    strongest = trend_pool_df.sort_values("latest_value", ascending=False).iloc[0]
    weakest = trend_pool_df.sort_values("latest_value", ascending=True).iloc[0]
    improving = trend_pool_df.sort_values("value_change", ascending=False).iloc[0]
    weakening = trend_pool_df.sort_values("value_change", ascending=True).iloc[0]
    return {
        "total_themes": int(len(trend_pool_df)),
        "date_count": int(trend_pool_df["date_count"].max()) if "date_count" in trend_pool_df.columns else 0,
        "strength_count": strength_count,
        "improving_count": improving_count,
        "pressure_count": pressure_count,
        "mixed_count": mixed_count,
        "strongest_theme": strongest.get("theme_name"),
        "weakest_theme": weakest.get("theme_name"),
        "biggest_improving_theme": improving.get("theme_name"),
        "biggest_weakening_theme": weakening.get("theme_name"),
        "summary_label": label,
        "summary_reason": _clean_reason(reason),
    }
