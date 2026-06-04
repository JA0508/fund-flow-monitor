from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


SNAPSHOT_PATTERN = re.compile(r"^sector_flow_(\d{4}-\d{2}-\d{2})\.csv$")


def parse_snapshot_date(path: Path) -> str | None:
    match = SNAPSHOT_PATTERN.match(Path(path).name)
    return match.group(1) if match else None


def list_snapshot_files(data_dir: str = "data/ticks") -> list[Path]:
    root = Path(data_dir)
    if not root.exists():
        return []
    files = [path for path in root.glob("sector_flow_*.csv") if parse_snapshot_date(path)]
    return sorted(files, key=lambda path: parse_snapshot_date(path) or "", reverse=True)


def _quality_label(captured_time_count: int, industry_rows: int, readable: bool) -> tuple[str, str]:
    if not readable:
        return "文件异常", "CSV 文件不可读或解析失败。"
    if industry_rows == 0:
        return "缺少行业资金流", "该文件没有行业资金流记录，无法构建主题主链路。"
    if captured_time_count >= 10:
        return "快照较完整", "该日期包含较多时间点，适合进行历史回放和日内热点观察。"
    if 2 <= captured_time_count < 10:
        return "快照可回放", "该日期包含多个时间点，可进行基础历史回放。"
    if captured_time_count == 1:
        return "仅单点快照", "该日期只有一个时间点，无法判断完整日内变化。"
    return "文件异常", "该文件缺少 captured_time 信息。"


def build_snapshot_catalog(data_dir: str = "data/ticks") -> pd.DataFrame:
    rows = []
    for path in list_snapshot_files(data_dir):
        snapshot_date = parse_snapshot_date(path)
        row = {
            "snapshot_date": snapshot_date,
            "file_path": str(path),
            "row_count": 0,
            "captured_time_count": 0,
            "latest_captured_time": None,
            "sector_type_count": 0,
            "industry_rows": 0,
            "concept_rows": 0,
            "file_size_kb": round(path.stat().st_size / 1024, 1) if path.exists() else 0,
            "is_readable": False,
            "quality_label": "文件异常",
            "quality_reason": "CSV 文件不可读或解析失败。",
        }
        try:
            df = pd.read_csv(path, dtype={"sector_code": str})
            row["is_readable"] = True
            row["row_count"] = int(len(df))
            row["captured_time_count"] = int(df["captured_time"].nunique()) if "captured_time" in df.columns else 0
            row["latest_captured_time"] = (
                str(df["captured_time"].dropna().iloc[-1])
                if "captured_time" in df.columns and not df["captured_time"].dropna().empty
                else None
            )
            row["sector_type_count"] = int(df["sector_type"].nunique()) if "sector_type" in df.columns else 0
            if "sector_type" in df.columns:
                row["industry_rows"] = int(df["sector_type"].eq("行业资金流").sum())
                row["concept_rows"] = int(df["sector_type"].eq("概念资金流").sum())
            row["quality_label"], row["quality_reason"] = _quality_label(
                row["captured_time_count"],
                row["industry_rows"],
                row["is_readable"],
            )
        except Exception as exc:
            row["quality_reason"] = f"CSV 文件不可读或解析失败：{exc}"
        rows.append(row)
    return pd.DataFrame(
        rows,
        columns=[
            "snapshot_date",
            "file_path",
            "row_count",
            "captured_time_count",
            "latest_captured_time",
            "sector_type_count",
            "industry_rows",
            "concept_rows",
            "file_size_kb",
            "is_readable",
            "quality_label",
            "quality_reason",
        ],
    )


def get_latest_snapshot_date(catalog_df: pd.DataFrame) -> str | None:
    if catalog_df is None or catalog_df.empty:
        return None
    readable = catalog_df[catalog_df["is_readable"].fillna(False)]
    if readable.empty:
        return None
    return str(readable.iloc[0]["snapshot_date"])


def load_snapshot_by_date(
    snapshot_date: str,
    data_dir: str = "data/ticks",
) -> pd.DataFrame:
    if not snapshot_date:
        return pd.DataFrame()
    path = Path(data_dir) / f"sector_flow_{snapshot_date}.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, dtype={"sector_code": str})
    except Exception:
        return pd.DataFrame()
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


def get_snapshot_summary(ticks_df: pd.DataFrame) -> dict:
    if ticks_df is None or ticks_df.empty:
        return {
            "row_count": 0,
            "captured_time_count": 0,
            "latest_captured_time": None,
            "sector_type_counts": {},
            "industry_rows": 0,
            "concept_rows": 0,
            "has_industry_data": False,
            "has_concept_data": False,
        }
    sector_counts = ticks_df["sector_type"].value_counts().to_dict() if "sector_type" in ticks_df.columns else {}
    industry_rows = int(sector_counts.get("行业资金流", 0))
    concept_rows = int(sector_counts.get("概念资金流", 0))
    latest_time = (
        str(ticks_df["captured_time"].dropna().iloc[-1])
        if "captured_time" in ticks_df.columns and not ticks_df["captured_time"].dropna().empty
        else None
    )
    return {
        "row_count": int(len(ticks_df)),
        "captured_time_count": int(ticks_df["captured_time"].nunique()) if "captured_time" in ticks_df.columns else 0,
        "latest_captured_time": latest_time,
        "sector_type_counts": sector_counts,
        "industry_rows": industry_rows,
        "concept_rows": concept_rows,
        "has_industry_data": industry_rows > 0,
        "has_concept_data": concept_rows > 0,
    }


def infer_view_data_status(
    selected_date: str,
    latest_date: str | None,
    live_status: str,
    is_demo: bool,
    history_mode_requested: bool = False,
    is_sample: bool = False,
) -> str:
    if is_demo:
        return "DEMO"
    if is_sample:
        return "SAMPLE" if selected_date else "EMPTY"
    if not selected_date:
        return "EMPTY"
    if history_mode_requested:
        return "HISTORY"
    if latest_date and selected_date != latest_date:
        return "HISTORY"
    if live_status == "LIVE":
        return "LIVE"
    if live_status == "CACHE":
        return "CACHE"
    return "EMPTY"
