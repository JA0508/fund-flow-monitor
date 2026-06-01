from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable

import pandas as pd

from src.config import DATA_SOURCE, TIMEZONE
from src.utils import safe_to_float


COLUMN_ALIASES = {
    "sector_code": ("板块代码", "代码", "行业代码", "概念代码"),
    "sector_name": ("板块名称", "名称", "行业名称", "概念名称"),
    "change_pct": ("涨跌幅", "今日涨跌幅", "涨跌幅%", "涨跌幅(%)"),
    "main_net_inflow_yuan": ("主力净流入-净额", "今日主力净流入-净额", "主力净流入净额"),
    "main_net_ratio": ("主力净流入-净占比", "今日主力净流入-净占比", "主力净流入净占比"),
    "super_large_net_inflow_yuan": (
        "超大单净流入-净额",
        "今日超大单净流入-净额",
        "超大单净流入净额",
    ),
    "large_net_inflow_yuan": ("大单净流入-净额", "今日大单净流入-净额", "大单净流入净额"),
    "medium_net_inflow_yuan": ("中单净流入-净额", "今日中单净流入-净额", "中单净流入净额"),
    "small_net_inflow_yuan": ("小单净流入-净额", "今日小单净流入-净额", "小单净流入净额"),
    "leading_stock": ("主力净流入最大股", "今日主力净流入最大股", "领涨股", "龙头股"),
    "leading_stock_code": ("主力净流入最大股代码", "今日主力净流入最大股代码"),
}

OUTPUT_COLUMNS = [
    "trade_date",
    "captured_at",
    "captured_time",
    "sector_type",
    "sector_code",
    "sector_name",
    "change_pct",
    "main_net_inflow_yuan",
    "main_net_inflow_billion",
    "main_net_ratio",
    "super_large_net_inflow_yuan",
    "large_net_inflow_yuan",
    "medium_net_inflow_yuan",
    "small_net_inflow_yuan",
    "leading_stock",
    "source",
]


def _resolve_column(columns: Iterable[str], aliases: Iterable[str]) -> str | None:
    available = list(columns)
    for alias in aliases:
        if alias in available:
            return alias
    normalized = {str(col).replace(" ", "").replace("_", ""): col for col in available}
    for alias in aliases:
        key = alias.replace(" ", "").replace("_", "")
        if key in normalized:
            return normalized[key]
    for col in available:
        col_text = str(col)
        for alias in aliases:
            if alias in col_text:
                return col
    return None


def _series_or_none(raw_df: pd.DataFrame, aliases: Iterable[str]) -> pd.Series:
    column = _resolve_column(raw_df.columns, aliases)
    if column is None:
        return pd.Series([None] * len(raw_df), index=raw_df.index)
    return raw_df[column]


def _normalize_timestamp(captured_at: datetime | None) -> pd.Timestamp:
    if captured_at is None:
        return pd.Timestamp.now(tz=TIMEZONE)
    ts = pd.Timestamp(captured_at)
    if ts.tzinfo is None:
        return ts.tz_localize(TIMEZONE)
    return ts.tz_convert(TIMEZONE)


def normalize_sector_flow(
    raw_df: pd.DataFrame,
    sector_type: str,
    captured_at: datetime | None,
) -> pd.DataFrame:
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    captured_ts = _normalize_timestamp(captured_at)
    normalized = pd.DataFrame(index=raw_df.index)

    for target, aliases in COLUMN_ALIASES.items():
        normalized[target] = _series_or_none(raw_df, aliases)

    for column in [
        "change_pct",
        "main_net_inflow_yuan",
        "main_net_ratio",
        "super_large_net_inflow_yuan",
        "large_net_inflow_yuan",
        "medium_net_inflow_yuan",
        "small_net_inflow_yuan",
    ]:
        normalized[column] = normalized[column].map(safe_to_float)

    normalized["sector_code"] = normalized["sector_code"].fillna("").astype(str)
    normalized["sector_name"] = normalized["sector_name"].astype("string").str.strip()
    normalized["leading_stock"] = normalized["leading_stock"].astype("string").str.strip()

    code = normalized.get("leading_stock_code")
    if code is not None:
        code_text = code.fillna("").astype(str).str.strip()
        has_code = code_text.ne("")
        normalized.loc[has_code, "leading_stock"] = (
            normalized.loc[has_code, "leading_stock"].fillna("")
            + " "
            + code_text.loc[has_code]
        ).str.strip()

    normalized["main_net_inflow_billion"] = (
        normalized["main_net_inflow_yuan"] / 100_000_000.0
    )
    normalized["captured_at"] = captured_ts
    normalized["captured_time"] = captured_ts.strftime("%H:%M:%S")
    normalized["trade_date"] = captured_ts.strftime("%Y-%m-%d")
    normalized["sector_type"] = sector_type
    normalized["source"] = DATA_SOURCE

    normalized = normalized.drop(columns=["leading_stock_code"], errors="ignore")
    normalized = normalized[
        normalized["sector_name"].notna()
        & normalized["sector_name"].ne("")
        & normalized["main_net_inflow_yuan"].map(lambda value: not math.isnan(value))
    ]
    return normalized[OUTPUT_COLUMNS].reset_index(drop=True)

