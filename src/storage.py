from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import DATA_DIR
from src.transform import OUTPUT_COLUMNS
from src.utils import ensure_dir


def get_today_file_path(trade_date: str) -> Path:
    ensure_dir(DATA_DIR)
    return DATA_DIR / f"sector_flow_{trade_date}.csv"


def ensure_snapshot_directory(directory: str = "data/ticks") -> str:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_snapshot_output_path(
    data_date: str | None = None,
    directory: str = "data/ticks",
    prefix: str = "sector_flow",
) -> str:
    if data_date is None:
        data_date = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d")
    ensure_snapshot_directory(directory)
    return str(Path(directory) / f"{prefix}_{data_date}.csv")


def _assert_real_snapshot(df: pd.DataFrame) -> None:
    mode_columns = [column for column in ("source", "data_mode", "mode") if column in df.columns]
    for column in mode_columns:
        values = df[column].astype(str).str.upper()
        if values.str.contains("DEMO", na=False).any():
            raise ValueError("DEMO 数据不允许写入真实 CSV")
        if values.str.contains("SAMPLE", na=False).any():
            raise ValueError("SAMPLE 样例数据不允许写入真实 CSV")


def append_snapshot(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    _assert_real_snapshot(df)

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


def append_snapshot_safely(
    df: pd.DataFrame,
    output_path: str,
    dedupe_keys: list[str] | None = None,
    force: bool = False,
) -> dict:
    warnings: list[str] = []
    errors: list[str] = []
    path = Path(output_path)
    before_rows = 0
    incoming_rows = int(len(df)) if df is not None else 0
    written_rows = 0
    duplicate_detected = False
    if df is None or df.empty:
        return {
            "output_path": str(path),
            "before_rows": before_rows,
            "incoming_rows": incoming_rows,
            "written_rows": 0,
            "after_rows": before_rows,
            "duplicate_detected": False,
            "write_status": "empty",
            "warnings": ["incoming DataFrame 为空。"],
            "errors": [],
        }
    try:
        _assert_real_snapshot(df)
    except ValueError as exc:
        return {
            "output_path": str(path),
            "before_rows": 0,
            "incoming_rows": incoming_rows,
            "written_rows": 0,
            "after_rows": 0,
            "duplicate_detected": False,
            "write_status": "blocked",
            "warnings": [],
            "errors": [str(exc)],
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    new_df = df.copy()
    dedupe_keys = dedupe_keys or [column for column in ("captured_time", "sector_type", "sector_name") if column in new_df.columns]
    if not dedupe_keys:
        warnings.append("缺少可用 dedupe_keys，无法执行重复检测。")
    if path.exists():
        try:
            existing = pd.read_csv(path, dtype={"sector_code": str})
            before_rows = int(len(existing))
        except Exception as exc:
            return {
                "output_path": str(path),
                "before_rows": 0,
                "incoming_rows": incoming_rows,
                "written_rows": 0,
                "after_rows": 0,
                "duplicate_detected": False,
                "write_status": "error",
                "warnings": warnings,
                "errors": [f"现有 CSV 不可读，已停止追加以避免破坏文件：{exc}"],
            }
        if dedupe_keys and all(column in existing.columns for column in dedupe_keys):
            existing_keys = set(map(tuple, existing[dedupe_keys].astype(str).to_numpy()))
            incoming_keys = new_df[dedupe_keys].astype(str).apply(tuple, axis=1)
            duplicate_mask = incoming_keys.isin(existing_keys)
            duplicate_detected = bool(duplicate_mask.any())
            if duplicate_detected and not force:
                skipped = int(duplicate_mask.sum())
                warnings.append(f"检测到 {skipped} 条重复 captured_time + sector 记录，已跳过。")
                new_df = new_df.loc[~duplicate_mask].copy()
        elif dedupe_keys:
            warnings.append("现有 CSV 缺少部分 dedupe_keys，跳过重复检测。")
    if new_df.empty:
        return {
            "output_path": str(path),
            "before_rows": before_rows,
            "incoming_rows": incoming_rows,
            "written_rows": 0,
            "after_rows": before_rows,
            "duplicate_detected": duplicate_detected,
            "write_status": "skipped_duplicate",
            "warnings": warnings,
            "errors": errors,
        }
    new_df.to_csv(path, mode="a", header=not path.exists(), index=False, encoding="utf-8-sig")
    written_rows = int(len(new_df))
    after_rows = before_rows + written_rows
    return {
        "output_path": str(path),
        "before_rows": before_rows,
        "incoming_rows": incoming_rows,
        "written_rows": written_rows,
        "after_rows": after_rows,
        "duplicate_detected": duplicate_detected,
        "write_status": "written" if written_rows else "skipped",
        "warnings": warnings,
        "errors": errors,
    }


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
