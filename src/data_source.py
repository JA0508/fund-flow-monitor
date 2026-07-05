from __future__ import annotations

import pandas as pd

from src.providers.akshare_sector_flow import (
    ProviderBoundaryError,
    fetch_and_normalize_sector_flow,
    fetch_raw_sector_flow,
)


def fetch_sector_flow(sector_type: str, indicator: str = "今日") -> pd.DataFrame:
    """Fetch raw Eastmoney sector fund-flow ranking data through AKShare."""
    try:
        result = fetch_raw_sector_flow(sector_type=sector_type, indicator=indicator)
    except ProviderBoundaryError as exc:
        raise RuntimeError(f"AKShare 获取 {sector_type} {indicator} 数据失败：{exc}") from exc
    if result.raw_df is None or result.raw_df.empty:
        raise RuntimeError(f"AKShare 返回空数据：{sector_type} {indicator}")
    return result.raw_df


def fetch_sector_flow_with_diagnostics(
    sector_type: str,
    indicator: str = "今日",
    attempts: int = 1,
) -> dict:
    """Fetch and normalize AKShare data with provider-boundary diagnostics."""
    result = fetch_and_normalize_sector_flow(
        sector_type=sector_type,
        indicator=indicator,
        attempts=attempts,
    )
    return {
        "raw_df": result.raw_df,
        "normalized_df": result.normalized_df,
        "diagnostic": result.diagnostic,
    }

