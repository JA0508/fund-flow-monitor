from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import DATA_DIR
from src.transform import OUTPUT_COLUMNS
from src.utils import ensure_dir


def get_today_file_path(trade_date: str) -> Path:
    ensure_dir(DATA_DIR)
    return DATA_DIR / f"sector_flow_{trade_date}.csv"


def append_snapshot(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    mode_columns = [column for column in ("source", "data_mode", "mode") if column in df.columns]
    for column in mode_columns:
        values = df[column].astype(str).str.upper()
        if values.str.contains("DEMO", na=False).any():
            raise ValueError("DEMO 数据不允许写入真实 CSV")
        if values.str.contains("SAMPLE", na=False).any():
            raise ValueError("SAMPLE 样例数据不允许写入真实 CSV")

    trade_date = str(df["trade_date"].iloc[0])
    path = get_today_file_path(trade_date)
    new_df = df.copy()
    new_df = new_df[OUTPUT_COLUMNS]

    if path.exists():
        existing = pd.read_csv(path, dtype={"sector_code": str})
        key_cols = ["captured_at", "sector_type", "sector_name"]
        existing_keys = set(map(tuple, existing[key_cols].astype(str).to_numpy()))
        new_keys = new_df[key_cols].astype(str).apply(tuple, axis=1)
        new_df = new_df.loc[~new_keys.isin(existing_keys)]

    if new_df.empty:
        return

    new_df.to_csv(path, mode="a", header=not path.exists(), index=False, encoding="utf-8-sig")


def load_today_ticks(trade_date: str) -> pd.DataFrame:
    path = get_today_file_path(trade_date)
    if not path.exists():
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    df = pd.read_csv(path, dtype={"sector_code": str})
    if "captured_at" in df.columns:
        df["captured_at"] = pd.to_datetime(df["captured_at"], errors="coerce")
    for column in [
        "change_pct",
        "main_net_inflow_yuan",
        "main_net_inflow_billion",
        "main_net_ratio",
        "super_large_net_inflow_yuan",
        "large_net_inflow_yuan",
        "medium_net_inflow_yuan",
        "small_net_inflow_yuan",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def find_latest_tick_file() -> Path | None:
    ensure_dir(DATA_DIR)
    files = sorted(DATA_DIR.glob("sector_flow_*.csv"))
    return files[-1] if files else None


def load_latest_ticks() -> pd.DataFrame:
    latest = find_latest_tick_file()
    if latest is None:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    trade_date = latest.stem.replace("sector_flow_", "")
    return load_today_ticks(trade_date)
