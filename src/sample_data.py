from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.snapshot_catalog import build_snapshot_catalog, get_latest_snapshot_date, list_snapshot_files, load_snapshot_by_date


SAMPLE_DIR = "sample_data/ticks"
SAMPLE_MODE = "SAMPLE"


def list_sample_snapshot_files(sample_dir: str = SAMPLE_DIR) -> list[Path]:
    return list_snapshot_files(sample_dir)


def build_sample_snapshot_catalog(sample_dir: str = SAMPLE_DIR) -> pd.DataFrame:
    catalog = build_snapshot_catalog(sample_dir)
    if catalog.empty:
        return catalog.assign(is_sample=pd.Series(dtype=bool)) if "is_sample" not in catalog.columns else catalog
    catalog = catalog.copy()
    catalog["is_sample"] = True
    catalog["quality_reason"] = catalog["quality_reason"].astype(str) + " 该文件为合成演示样例数据，不代表真实行情。"
    return catalog


def get_latest_sample_date(catalog_df: pd.DataFrame) -> str | None:
    return get_latest_snapshot_date(catalog_df)


def mark_sample_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out["source"] = SAMPLE_MODE
    out["data_mode"] = SAMPLE_MODE
    return out


def load_sample_snapshot_by_date(
    snapshot_date: str,
    sample_dir: str = SAMPLE_DIR,
) -> pd.DataFrame:
    df = load_snapshot_by_date(snapshot_date, data_dir=sample_dir)
    return mark_sample_dataframe(df)
