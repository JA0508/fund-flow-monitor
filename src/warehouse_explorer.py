from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from src.local_warehouse import get_existing_warehouse_path, safe_close_connection
from src.snapshot_quality import build_snapshot_file_catalog


FORBIDDEN_EXPLORER_WORDS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "抄底",
    "逃顶",
    "推荐买",
    "推荐卖",
    "建议买",
    "建议卖",
    "建仓",
    "清仓",
    "未来会涨",
    "未来会跌",
    "适合配置",
    "应该调仓",
)

SOURCE_SUMMARY_COLUMNS = [
    "source_type",
    "file_count",
    "row_count",
    "data_date_count",
    "captured_time_count",
    "latest_data_date",
    "latest_captured_time",
]
DATE_OVERVIEW_COLUMNS = [
    "source_type",
    "data_date",
    "row_count",
    "captured_time_count",
    "sector_count",
    "latest_captured_time",
    "imported_file_count",
]
CAPTURED_TIME_COLUMNS = [
    "source_type",
    "data_date",
    "captured_time",
    "row_count",
    "sector_count",
    "top_abs_inflow_sector",
    "top_abs_inflow_value",
]
SECTOR_SAMPLE_COLUMNS = [
    "source_type",
    "data_date",
    "captured_time",
    "sector_type",
    "sector_name",
    "main_net_inflow_billion",
    "rank_value",
    "change_percent",
    "imported_file",
]
FILE_RECORD_COLUMNS = [
    "source_type",
    "file_name",
    "data_date",
    "file_size_kb",
    "row_count",
    "captured_time_count",
    "imported_at",
    "quality_label",
    "warning_count",
    "error_count",
]


def _empty_df(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    try:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
        return row is not None
    except Exception:
        return False


def load_warehouse_if_exists(path: str | None = None) -> tuple[sqlite3.Connection | None, dict]:
    warehouse_path = get_existing_warehouse_path(path)
    status = {
        "warehouse_path": warehouse_path,
        "exists": False,
        "can_connect": False,
        "status_label": "warehouse 未创建",
        "status_reason": "未找到本地 SQLite warehouse。CSV 路径仍可正常运行，可按命令手动重建查询索引。",
        "errors": [],
        "warnings": [],
    }
    if not Path(warehouse_path).exists():
        return None, status
    status["exists"] = True
    try:
        conn = sqlite3.connect(warehouse_path)
        conn.row_factory = sqlite3.Row
        status.update(
            {
                "can_connect": True,
                "status_label": "warehouse 可读取",
                "status_reason": "已连接本地 SQLite warehouse。当前面板仅做只读查询，不会重建或写入。",
            }
        )
        return conn, status
    except Exception as exc:
        status["status_label"] = "warehouse 读取失败"
        status["status_reason"] = f"SQLite warehouse 存在但无法连接：{exc}"
        status["errors"] = [str(exc)]
        return None, status


def get_warehouse_source_type_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    if conn is None or not _table_exists(conn, "snapshot_rows"):
        return _empty_df(SOURCE_SUMMARY_COLUMNS)
    try:
        rows_df = pd.read_sql_query(
            """
            SELECT source_type,
                   COUNT(*) AS row_count,
                   COUNT(DISTINCT data_date) AS data_date_count,
                   COUNT(DISTINCT captured_time) AS captured_time_count,
                   MAX(data_date) AS latest_data_date,
                   MAX(captured_time) AS latest_captured_time
            FROM snapshot_rows
            GROUP BY source_type
            ORDER BY source_type
            """,
            conn,
        )
        files_df = get_warehouse_file_records(conn)
        if files_df.empty:
            rows_df["file_count"] = 0
        else:
            file_counts = files_df.groupby("source_type")["file_name"].nunique().rename("file_count").reset_index()
            rows_df = rows_df.merge(file_counts, on="source_type", how="left")
            rows_df["file_count"] = rows_df["file_count"].fillna(0).astype(int)
        return rows_df[SOURCE_SUMMARY_COLUMNS]
    except Exception:
        return _empty_df(SOURCE_SUMMARY_COLUMNS)


def get_warehouse_date_overview(
    conn: sqlite3.Connection,
    source_type: str | None = None,
) -> pd.DataFrame:
    if conn is None or not _table_exists(conn, "snapshot_rows"):
        return _empty_df(DATE_OVERVIEW_COLUMNS)
    clauses: list[str] = []
    params: list[Any] = []
    if source_type and str(source_type).upper() != "ALL":
        clauses.append("source_type = ?")
        params.append(str(source_type).upper())
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    try:
        return pd.read_sql_query(
            f"""
            SELECT source_type, data_date, COUNT(*) AS row_count,
                   COUNT(DISTINCT captured_time) AS captured_time_count,
                   COUNT(DISTINCT sector_name) AS sector_count,
                   MAX(captured_time) AS latest_captured_time,
                   COUNT(DISTINCT imported_file) AS imported_file_count
            FROM snapshot_rows
            {where}
            GROUP BY source_type, data_date
            ORDER BY source_type, data_date DESC
            """,
            conn,
            params=params,
        )[DATE_OVERVIEW_COLUMNS]
    except Exception:
        return _empty_df(DATE_OVERVIEW_COLUMNS)


def get_warehouse_captured_time_overview(
    conn: sqlite3.Connection,
    source_type: str | None = None,
    data_date: str | None = None,
) -> pd.DataFrame:
    if conn is None or not _table_exists(conn, "snapshot_rows"):
        return _empty_df(CAPTURED_TIME_COLUMNS)
    clauses: list[str] = []
    params: list[Any] = []
    if source_type and str(source_type).upper() != "ALL":
        clauses.append("source_type = ?")
        params.append(str(source_type).upper())
    if data_date and str(data_date).upper() != "ALL":
        clauses.append("data_date = ?")
        params.append(str(data_date))
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    try:
        rows = pd.read_sql_query(
            f"""
            SELECT source_type, data_date, captured_time, sector_name, main_net_inflow_billion
            FROM snapshot_rows
            {where}
            """,
            conn,
            params=params,
        )
        if rows.empty:
            return _empty_df(CAPTURED_TIME_COLUMNS)
        rows["abs_flow"] = pd.to_numeric(rows["main_net_inflow_billion"], errors="coerce").abs()
        top_idx = rows.groupby(["source_type", "data_date", "captured_time"])["abs_flow"].idxmax()
        top_df = rows.loc[top_idx, ["source_type", "data_date", "captured_time", "sector_name", "main_net_inflow_billion"]].rename(
            columns={"sector_name": "top_abs_inflow_sector", "main_net_inflow_billion": "top_abs_inflow_value"}
        )
        overview = (
            rows.groupby(["source_type", "data_date", "captured_time"])
            .agg(row_count=("sector_name", "size"), sector_count=("sector_name", "nunique"))
            .reset_index()
        )
        out = overview.merge(top_df, on=["source_type", "data_date", "captured_time"], how="left")
        return out.sort_values(["source_type", "data_date", "captured_time"], ascending=[True, False, False])[
            CAPTURED_TIME_COLUMNS
        ]
    except Exception:
        return _empty_df(CAPTURED_TIME_COLUMNS)


def get_warehouse_sector_sample(
    conn: sqlite3.Connection,
    source_type: str | None = None,
    data_date: str | None = None,
    captured_time: str | None = None,
    top_n: int = 20,
    sort_by_abs_flow: bool = True,
) -> pd.DataFrame:
    if conn is None or not _table_exists(conn, "snapshot_rows"):
        return _empty_df(SECTOR_SAMPLE_COLUMNS)
    safe_top_n = max(1, min(int(top_n or 20), 200))
    clauses: list[str] = []
    params: list[Any] = []
    if source_type and str(source_type).upper() != "ALL":
        clauses.append("source_type = ?")
        params.append(str(source_type).upper())
    if data_date and str(data_date).upper() != "ALL":
        clauses.append("data_date = ?")
        params.append(str(data_date))
    if captured_time and str(captured_time).upper() != "ALL":
        clauses.append("captured_time = ?")
        params.append(str(captured_time))
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    order = "ABS(main_net_inflow_billion) DESC, data_date DESC, captured_time DESC" if sort_by_abs_flow else "data_date DESC, captured_time DESC, id ASC"
    try:
        return pd.read_sql_query(
            f"""
            SELECT {", ".join(SECTOR_SAMPLE_COLUMNS)}
            FROM snapshot_rows
            {where}
            ORDER BY {order}
            LIMIT {safe_top_n}
            """,
            conn,
            params=params,
        )[SECTOR_SAMPLE_COLUMNS]
    except Exception:
        return _empty_df(SECTOR_SAMPLE_COLUMNS)


def get_warehouse_file_records(
    conn: sqlite3.Connection,
    source_type: str | None = None,
) -> pd.DataFrame:
    if conn is None or not _table_exists(conn, "snapshot_files"):
        return _empty_df(FILE_RECORD_COLUMNS)
    params: list[Any] = []
    where = ""
    if source_type and str(source_type).upper() != "ALL":
        where = "WHERE source_type = ?"
        params.append(str(source_type).upper())
    try:
        return pd.read_sql_query(
            f"""
            SELECT source_type, file_name, data_date, file_size_kb, row_count,
                   captured_time_count, imported_at, quality_label, warning_count, error_count
            FROM snapshot_files
            {where}
            ORDER BY source_type, data_date DESC, file_name
            """,
            conn,
            params=params,
        )[FILE_RECORD_COLUMNS]
    except Exception:
        return _empty_df(FILE_RECORD_COLUMNS)


def get_warehouse_available_source_types(conn: sqlite3.Connection | None) -> list[str]:
    if conn is None or not _table_exists(conn, "snapshot_rows"):
        return []
    try:
        rows = conn.execute(
            "SELECT DISTINCT source_type FROM snapshot_rows WHERE source_type IS NOT NULL ORDER BY source_type"
        ).fetchall()
        return [str(row[0]).upper() for row in rows if row[0]]
    except Exception:
        return []


def get_warehouse_date_range(conn: sqlite3.Connection | None, source_type: str | None = None) -> dict:
    source = str(source_type or "ALL").upper()
    result = {"min_date": None, "max_date": None, "date_count": 0, "source_type": source}
    if conn is None or not _table_exists(conn, "snapshot_rows"):
        return result
    clauses: list[str] = []
    params: list[Any] = []
    if source_type and source != "ALL":
        clauses.append("source_type = ?")
        params.append(source)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    try:
        row = conn.execute(
            f"""
            SELECT MIN(data_date) AS min_date, MAX(data_date) AS max_date,
                   COUNT(DISTINCT data_date) AS date_count
            FROM snapshot_rows
            {where}
            """,
            tuple(params),
        ).fetchone()
        if row:
            result.update({"min_date": row["min_date"], "max_date": row["max_date"], "date_count": int(row["date_count"] or 0)})
    except Exception:
        return result
    return result


def _as_int(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(value)
    except Exception:
        return 0


def compare_csv_catalog_with_warehouse(
    csv_catalog_df: pd.DataFrame,
    warehouse_files_df: pd.DataFrame,
    source_type: str,
) -> dict:
    source = str(source_type or "LOCAL").upper()
    warnings: list[str] = []
    errors: list[str] = []
    csv_df = csv_catalog_df.copy() if csv_catalog_df is not None else pd.DataFrame()
    wh_df = warehouse_files_df.copy() if warehouse_files_df is not None else pd.DataFrame()
    if not wh_df.empty and "source_type" in wh_df.columns:
        wh_df = wh_df[wh_df["source_type"].astype(str).str.upper().eq(source)].copy()
    csv_files = set(csv_df.get("file_name", pd.Series(dtype=str)).dropna().astype(str))
    wh_files = set(wh_df.get("file_name", pd.Series(dtype=str)).dropna().astype(str))
    matched = sorted(csv_files & wh_files)
    csv_missing = sorted(csv_files - wh_files)
    wh_missing = sorted(wh_files - csv_files)
    row_mismatch: list[str] = []
    time_mismatch: list[str] = []
    if matched and {"file_name", "row_count", "captured_time_count"}.issubset(csv_df.columns) and {"file_name", "row_count", "captured_time_count"}.issubset(wh_df.columns):
        csv_idx = csv_df.set_index("file_name")
        wh_idx = wh_df.set_index("file_name")
        for file_name in matched:
            if _as_int(csv_idx.loc[file_name, "row_count"]) != _as_int(wh_idx.loc[file_name, "row_count"]):
                row_mismatch.append(file_name)
            if _as_int(csv_idx.loc[file_name, "captured_time_count"]) != _as_int(wh_idx.loc[file_name, "captured_time_count"]):
                time_mismatch.append(file_name)
    if row_mismatch:
        warnings.append(f"{source} 存在 {len(row_mismatch)} 个文件行数与 warehouse 记录不一致。")
    if time_mismatch:
        warnings.append(f"{source} 存在 {len(time_mismatch)} 个文件 captured_time 数与 warehouse 记录不一致。")
    if csv_missing:
        warnings.append(f"{source} 有 {len(csv_missing)} 个 CSV 文件尚未导入 warehouse。")
    if wh_missing:
        warnings.append(f"{source} 有 {len(wh_missing)} 个 warehouse 文件记录在 CSV 目录中不存在。")
    if not csv_files and not wh_files:
        label = "无可比对数据"
        reason = f"{source} CSV 目录和 warehouse 均无文件记录。"
    elif csv_files and not wh_files:
        label = "仅 CSV 可用"
        reason = f"{source} CSV 目录有文件，但尚未导入 warehouse；可按需手动重建索引。"
    elif wh_files and not csv_files:
        label = "仅 warehouse 可用"
        reason = f"{source} warehouse 有文件记录，但当前 CSV 目录没有对应文件；请确认目录或按需重建。"
    elif row_mismatch or time_mismatch or csv_missing or wh_missing:
        label = "warehouse 需要重建"
        reason = f"{source} CSV 与 warehouse 文件记录存在差异，建议按需手动重建查询索引。"
    else:
        label = "CSV 与 warehouse 一致"
        reason = f"{source} CSV 文件目录与 warehouse 文件记录基本一致。"
    return {
        "source_type": source,
        "csv_file_count": len(csv_files),
        "warehouse_file_count": len(wh_files),
        "matched_file_count": len(matched),
        "csv_missing_in_warehouse": csv_missing,
        "warehouse_missing_in_csv": wh_missing,
        "row_count_mismatch": row_mismatch,
        "captured_time_count_mismatch": time_mismatch,
        "consistency_label": label,
        "consistency_reason": reason,
        "warnings": warnings,
        "errors": errors,
    }


def build_csv_warehouse_consistency_report(
    conn: sqlite3.Connection | None,
    local_csv_dir: str = "data/ticks",
    sample_csv_dir: str = "sample_data/ticks",
) -> dict:
    warnings: list[str] = []
    errors: list[str] = []
    if conn is None:
        return {
            "warehouse_exists": False,
            "local_consistency": compare_csv_catalog_with_warehouse(pd.DataFrame(), pd.DataFrame(), "LOCAL"),
            "sample_consistency": compare_csv_catalog_with_warehouse(pd.DataFrame(), pd.DataFrame(), "SAMPLE"),
            "overall_label": "warehouse 未创建",
            "overall_reason": "本地 SQLite warehouse 尚未创建。CSV 仍可直接驱动当前应用，可按需手动重建查询索引。",
            "warning_count": 0,
            "error_count": 0,
            "warnings": [],
            "errors": [],
        }
    local_catalog = build_snapshot_file_catalog(local_csv_dir, pattern="sector_flow_*.csv")
    sample_catalog = build_snapshot_file_catalog(sample_csv_dir, pattern="sector_flow_*.csv")
    files_df = get_warehouse_file_records(conn)
    local = compare_csv_catalog_with_warehouse(local_catalog, files_df, "LOCAL")
    sample = compare_csv_catalog_with_warehouse(sample_catalog, files_df, "SAMPLE")
    warnings.extend(local.get("warnings", []))
    warnings.extend(sample.get("warnings", []))
    errors.extend(local.get("errors", []))
    errors.extend(sample.get("errors", []))
    local_label = local.get("consistency_label")
    sample_label = sample.get("consistency_label")
    if errors:
        label = "存在不一致"
        reason = "CSV 与 warehouse 一致性审计存在错误，请检查 warehouse 或 CSV 目录。"
    elif local_label == "CSV 与 warehouse 一致" and sample_label == "CSV 与 warehouse 一致":
        label = "CSV 与 warehouse 基本一致"
        reason = "LOCAL 与 SAMPLE 的 CSV 文件目录和 warehouse 文件记录基本一致。"
    elif sample_label == "CSV 与 warehouse 一致" and local_label in {"仅 CSV 可用", "无可比对数据"}:
        label = "SAMPLE 一致，LOCAL 未导入"
        reason = "SAMPLE CSV 与 warehouse 基本一致；LOCAL CSV 尚未导入或当前无 LOCAL CSV，这是公开演示中的正常状态。"
    elif sample_label == "CSV 与 warehouse 一致" and local_label == "仅 warehouse 可用":
        label = "SAMPLE 一致，LOCAL 目录待确认"
        reason = "SAMPLE CSV 与 warehouse 基本一致；LOCAL warehouse 记录在当前 CSV 目录中没有对应文件。"
    elif "warehouse 需要重建" in {local_label, sample_label}:
        label = "warehouse 需要重建"
        reason = "至少一个 source_type 的 CSV 与 warehouse 文件记录存在差异，可按需手动重建查询索引。"
    elif local_label == "仅 CSV 可用" or sample_label == "仅 CSV 可用":
        label = "仅 CSV 可用"
        reason = "CSV 文件可用但尚未完整导入 warehouse。CSV 仍是主数据来源。"
    else:
        label = "存在不一致" if warnings else "无可比对数据"
        reason = "CSV 与 warehouse 的可比对数据有限，请按需查看明细。"
    return {
        "warehouse_exists": True,
        "local_consistency": local,
        "sample_consistency": sample,
        "overall_label": label,
        "overall_reason": reason,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
    }


def build_warehouse_explorer_summary(conn: sqlite3.Connection | None) -> dict:
    if conn is None:
        return {
            "explorer_available": False,
            "source_type_count": 0,
            "date_count": 0,
            "captured_time_count": 0,
            "row_count": 0,
            "latest_local_date": None,
            "latest_sample_date": None,
            "explorer_label": "Explorer 不可用",
            "explorer_reason": "本地 SQLite warehouse 未创建，当前只使用 CSV 路径运行。",
        }
    source_df = get_warehouse_source_type_summary(conn)
    date_df = get_warehouse_date_overview(conn)
    if source_df.empty:
        return {
            "explorer_available": False,
            "source_type_count": 0,
            "date_count": 0,
            "captured_time_count": 0,
            "row_count": 0,
            "latest_local_date": None,
            "latest_sample_date": None,
            "explorer_label": "warehouse 无可查询数据",
            "explorer_reason": "SQLite warehouse 存在但没有 snapshot_rows 记录，可从 CSV 手动重建。",
        }
    latest_local = None
    latest_sample = None
    if not date_df.empty:
        local_dates = date_df[date_df["source_type"].eq("LOCAL")]["data_date"].dropna()
        sample_dates = date_df[date_df["source_type"].eq("SAMPLE")]["data_date"].dropna()
        latest_local = local_dates.max() if not local_dates.empty else None
        latest_sample = sample_dates.max() if not sample_dates.empty else None
    return {
        "explorer_available": True,
        "source_type_count": int(source_df["source_type"].nunique()),
        "date_count": int(date_df["data_date"].nunique()) if not date_df.empty else 0,
        "captured_time_count": int(source_df["captured_time_count"].sum()),
        "row_count": int(source_df["row_count"].sum()),
        "latest_local_date": latest_local,
        "latest_sample_date": latest_sample,
        "explorer_label": "Explorer 可用",
        "explorer_reason": "可对已有 SQLite warehouse 做只读日期、时间点和板块样本查询。页面不会重建或写入 warehouse。",
    }


def summarize_csv_warehouse_consistency(report: dict) -> str:
    if not report or not report.get("warehouse_exists"):
        return "本地 SQLite warehouse 尚未创建。CSV 仍是主数据来源，应用可继续按 CSV 路径运行。"
    return (
        f"CSV-Warehouse 一致性状态：{report.get('overall_label', '未知')}。"
        f"{report.get('overall_reason', '')}"
        "SQLite 只是 CSV 的可重建查询索引；如存在差异，可按需手动重建。"
    )


def validate_warehouse_explorer_text(text: str) -> list[str]:
    return [word for word in FORBIDDEN_EXPLORER_WORDS if word in str(text or "")]


def close_loaded_warehouse(conn: sqlite3.Connection | None) -> None:
    safe_close_connection(conn)
