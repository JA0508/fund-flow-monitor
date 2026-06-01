from __future__ import annotations

import pandas as pd

from src.config import TIMEZONE


CONCEPT_SECTOR_TYPE = "概念资金流"


def _normalize_captured_at(value) -> pd.Timestamp | None:
    if value is None or pd.isna(value):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    if ts.tzinfo is not None:
        return ts.tz_convert(TIMEZONE).tz_localize(None)
    return ts


def _concept_ticks(ticks_df: pd.DataFrame) -> pd.DataFrame:
    if ticks_df is None or ticks_df.empty or "sector_type" not in ticks_df.columns:
        return pd.DataFrame()
    df = ticks_df[ticks_df["sector_type"].eq(CONCEPT_SECTOR_TYPE)].copy()
    if "captured_at" in df.columns and not df.empty:
        df["captured_at"] = pd.to_datetime(df["captured_at"], errors="coerce")
    return df


def get_concept_latest_snapshot(ticks_df: pd.DataFrame) -> pd.DataFrame:
    df = _concept_ticks(ticks_df)
    if df.empty or "captured_at" not in df.columns:
        return pd.DataFrame()
    df = df.dropna(subset=["captured_at"])
    if df.empty:
        return pd.DataFrame()
    latest_at = df["captured_at"].max()
    return df[df["captured_at"].eq(latest_at)].copy()


def get_concept_cache_summary(ticks_df: pd.DataFrame) -> dict:
    df = _concept_ticks(ticks_df)
    if df.empty:
        return {
            "has_concept_cache": False,
            "concept_rows": 0,
            "concept_unique_times": 0,
            "latest_concept_time": None,
            "latest_concept_captured_at": None,
        }
    latest = get_concept_latest_snapshot(df)
    latest_time = None
    latest_at = None
    if not latest.empty:
        latest_time = str(latest["captured_time"].iloc[0]) if "captured_time" in latest.columns else None
        latest_at = latest["captured_at"].iloc[0] if "captured_at" in latest.columns else None
    return {
        "has_concept_cache": True,
        "concept_rows": int(len(df)),
        "concept_unique_times": int(df["captured_time"].nunique()) if "captured_time" in df.columns else 0,
        "latest_concept_time": latest_time,
        "latest_concept_captured_at": latest_at,
    }


def should_refresh_concept_cache(latest_concept_time, now, max_age_minutes: int = 5) -> bool:
    latest = _normalize_captured_at(latest_concept_time)
    current = _normalize_captured_at(now)
    if latest is None or current is None:
        return True
    return (current - latest) >= pd.Timedelta(minutes=max_age_minutes)


def _hotspot_status(value: float) -> str:
    if value >= 20:
        return "强流入概念"
    if 5 <= value < 20:
        return "流入概念"
    if -5 < value < 5:
        return "分歧概念"
    if -20 < value <= -5:
        return "流出概念"
    return "强流出概念"


def summarize_concept_hotspots(concept_latest_df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if concept_latest_df is None or concept_latest_df.empty:
        return pd.DataFrame(
            columns=[
                "concept_name",
                "main_net_inflow_billion",
                "change_pct",
                "main_net_ratio",
                "leading_stock",
                "hotspot_status",
            ]
        )
    df = concept_latest_df.copy()
    name_col = "sector_name" if "sector_name" in df.columns else "concept_name"
    df["main_net_inflow_billion"] = pd.to_numeric(df.get("main_net_inflow_billion"), errors="coerce")
    df = df.dropna(subset=["main_net_inflow_billion"])
    if df.empty:
        return pd.DataFrame()
    df = df.sort_values("main_net_inflow_billion", key=lambda s: s.abs(), ascending=False).head(top_n)
    return pd.DataFrame(
        {
            "concept_name": df[name_col].astype(str).values,
            "main_net_inflow_billion": df["main_net_inflow_billion"].values,
            "change_pct": pd.to_numeric(df.get("change_pct"), errors="coerce").values,
            "main_net_ratio": pd.to_numeric(df.get("main_net_ratio"), errors="coerce").values,
            "leading_stock": df.get("leading_stock", pd.Series(["--"] * len(df), index=df.index)).fillna("--").astype(str).values,
            "hotspot_status": df["main_net_inflow_billion"].map(_hotspot_status).values,
        }
    ).reset_index(drop=True)
