from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.providers.akshare_sector_flow import (
    FIELD_ALIASES as COLUMN_ALIASES,
    OUTPUT_COLUMNS,
    ProviderBoundaryError,
    normalize_provider_dataframe,
)


def normalize_sector_flow(
    raw_df: pd.DataFrame,
    sector_type: str,
    captured_at: datetime | None,
) -> pd.DataFrame:
    """Normalize AKShare sector fund-flow rows into the internal snapshot schema.

    This compatibility wrapper keeps the historical project API while delegating
    provider-specific schema mapping to the AKShare adapter.
    """
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    try:
        result = normalize_provider_dataframe(
            raw_df,
            sector_type=sector_type,
            captured_at=captured_at,
            strict_schema=False,
        )
        return result.normalized_df if result.normalized_df is not None else pd.DataFrame(columns=OUTPUT_COLUMNS)
    except ProviderBoundaryError:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
