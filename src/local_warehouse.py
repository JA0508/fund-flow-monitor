from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from src.snapshot_quality import audit_snapshot_csv_file, build_snapshot_file_catalog, normalize_snapshot_columns
from src.utils import get_china_now


DEFAULT_WAREHOUSE_PATH = "data/warehouse/fund_flow.sqlite"
FORBIDDEN_WAREHOUSE_WORDS = (
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

SNAPSHOT_ROW_COLUMNS = [
    "source_type",
    "data_date",
    "captured_time",
    "sector_type",
    "sector_name",
    "main_net_inflow_billion",
    "rank_value",
    "change_percent",
    "raw_source",
    "imported_file",
    "imported_at",
]


def get_default_warehouse_path() -> str:
    return DEFAULT_WAREHOUSE_PATH


def get_existing_warehouse_path(path: str | None = None) -> str:
    return str(Path(path or get_default_warehouse_path()))


def warehouse_exists(path: str | None = None) -> bool:
    return Path(get_existing_warehouse_path(path)).exists()


def safe_close_connection(conn: sqlite3.Connection | None) -> None:
    if conn is None:
        return
    try:
        conn.close()
    except Exception:
        return


def ensure_warehouse_directory(path: str | None = None) -> str:
    warehouse_path = Path(path or get_default_warehouse_path())
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    return str(warehouse_path.parent)


def connect_warehouse(path: str | None = None) -> sqlite3.Connection:
    warehouse_path = Path(path or get_default_warehouse_path())
    if path is not None or str(warehouse_path) != ":memory:":
        ensure_warehouse_directory(str(warehouse_path))
    conn = sqlite3.connect(str(warehouse_path))
    conn.row_factory = sqlite3.Row
    return conn


def initialize_warehouse(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS snapshot_files (
            id INTEGER PRIMARY KEY,
            source_type TEXT,
            file_path TEXT,
            file_name TEXT,
            data_date TEXT,
            file_size_kb REAL,
            row_count INTEGER,
            captured_time_count INTEGER,
            imported_at TEXT,
            quality_label TEXT,
            warning_count INTEGER,
            error_count INTEGER
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshot_files_unique
        ON snapshot_files(source_type, file_path);

        CREATE TABLE IF NOT EXISTS snapshot_rows (
            id INTEGER PRIMARY KEY,
            source_type TEXT,
            data_date TEXT,
            captured_time TEXT,
            sector_type TEXT,
            sector_name TEXT,
            main_net_inflow_billion REAL,
            rank_value INTEGER,
            change_percent REAL,
            raw_source TEXT,
            imported_file TEXT,
            imported_at TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshot_rows_unique
        ON snapshot_rows(source_type, data_date, captured_time, sector_type, sector_name, imported_file);

        CREATE TABLE IF NOT EXISTS warehouse_meta (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        );
        """
    )
    conn.commit()


def _now_text() -> str:
    return get_china_now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _infer_data_date(df: pd.DataFrame, fallback: str | None = None) -> str | None:
    if fallback:
        return fallback
    for column in ("trade_date", "data_date"):
        if column in df.columns and not df[column].dropna().empty:
            return str(df[column].dropna().iloc[0])[:10]
    if "captured_at" in df.columns and not df["captured_at"].dropna().empty:
        captured = pd.to_datetime(df["captured_at"], errors="coerce").dropna()
        if not captured.empty:
            return captured.iloc[0].strftime("%Y-%m-%d")
    return None


def normalize_snapshot_df_for_warehouse(
    df: pd.DataFrame,
    source_type: str,
    data_date: str | None = None,
    imported_file: str | None = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=SNAPSHOT_ROW_COLUMNS)
    work = normalize_snapshot_columns(df)
    if "sector_name" not in work.columns:
        work["sector_name"] = None
    if "captured_time" not in work.columns:
        work["captured_time"] = None
    if "sector_type" not in work.columns:
        work["sector_type"] = None
    if "main_net_inflow_billion" not in work.columns:
        work["main_net_inflow_billion"] = None
    if "rank_value" not in work.columns:
        rank_source = "序号" if "序号" in work.columns else None
        work["rank_value"] = pd.to_numeric(work[rank_source], errors="coerce") if rank_source else None
    if "change_percent" not in work.columns:
        if "change_pct" in work.columns:
            work["change_percent"] = pd.to_numeric(work["change_pct"], errors="coerce")
        elif "涨跌幅" in work.columns:
            work["change_percent"] = pd.to_numeric(work["涨跌幅"], errors="coerce")
        else:
            work["change_percent"] = None
    inferred_date = _infer_data_date(work, data_date)
    out = pd.DataFrame(
        {
            "source_type": str(source_type or "LOCAL").upper(),
            "data_date": inferred_date,
            "captured_time": work["captured_time"].map(_safe_text),
            "sector_type": work["sector_type"].map(_safe_text),
            "sector_name": work["sector_name"].map(_safe_text),
            "main_net_inflow_billion": pd.to_numeric(work["main_net_inflow_billion"], errors="coerce"),
            "rank_value": pd.to_numeric(work["rank_value"], errors="coerce"),
            "change_percent": pd.to_numeric(work["change_percent"], errors="coerce"),
            "raw_source": work["source"].map(_safe_text) if "source" in work.columns else None,
            "imported_file": imported_file,
            "imported_at": _now_text(),
        }
    )
    return out[SNAPSHOT_ROW_COLUMNS]


def upsert_snapshot_file_record(
    conn: sqlite3.Connection,
    file_record: dict,
) -> dict:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        record = {
            "source_type": str(file_record.get("source_type") or "LOCAL").upper(),
            "file_path": str(file_record.get("file_path") or ""),
            "file_name": str(file_record.get("file_name") or Path(str(file_record.get("file_path") or "")).name),
            "data_date": file_record.get("data_date"),
            "file_size_kb": file_record.get("file_size_kb"),
            "row_count": file_record.get("row_count"),
            "captured_time_count": file_record.get("captured_time_count"),
            "imported_at": file_record.get("imported_at") or _now_text(),
            "quality_label": file_record.get("quality_label"),
            "warning_count": file_record.get("warning_count", 0),
            "error_count": file_record.get("error_count", 0),
        }
        existing = conn.execute(
            "SELECT id FROM snapshot_files WHERE source_type = ? AND file_path = ?",
            (record["source_type"], record["file_path"]),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE snapshot_files
                SET file_name = ?, data_date = ?, file_size_kb = ?, row_count = ?,
                    captured_time_count = ?, imported_at = ?, quality_label = ?,
                    warning_count = ?, error_count = ?
                WHERE id = ?
                """,
                (
                    record["file_name"],
                    record["data_date"],
                    record["file_size_kb"],
                    record["row_count"],
                    record["captured_time_count"],
                    record["imported_at"],
                    record["quality_label"],
                    record["warning_count"],
                    record["error_count"],
                    existing["id"],
                ),
            )
            conn.commit()
            return {"write_status": "updated", "inserted": False, "updated": True, "errors": errors, "warnings": warnings}
        conn.execute(
            """
            INSERT INTO snapshot_files (
                source_type, file_path, file_name, data_date, file_size_kb,
                row_count, captured_time_count, imported_at, quality_label,
                warning_count, error_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["source_type"],
                record["file_path"],
                record["file_name"],
                record["data_date"],
                record["file_size_kb"],
                record["row_count"],
                record["captured_time_count"],
                record["imported_at"],
                record["quality_label"],
                record["warning_count"],
                record["error_count"],
            ),
        )
        conn.commit()
        return {"write_status": "inserted", "inserted": True, "updated": False, "errors": errors, "warnings": warnings}
    except Exception as exc:
        errors.append(str(exc))
        return {"write_status": "error", "inserted": False, "updated": False, "errors": errors, "warnings": warnings}


def insert_snapshot_rows(
    conn: sqlite3.Connection,
    rows_df: pd.DataFrame,
    replace_existing: bool = False,
) -> dict:
    if rows_df is None or rows_df.empty:
        return {
            "incoming_rows": 0,
            "inserted_rows": 0,
            "skipped_duplicate_rows": 0,
            "error_count": 0,
            "warnings": ["rows_df 为空，未写入。"],
            "errors": [],
        }
    warnings: list[str] = []
    errors: list[str] = []
    df = rows_df.copy()
    for column in SNAPSHOT_ROW_COLUMNS:
        if column not in df.columns:
            df[column] = None
    df = df[SNAPSHOT_ROW_COLUMNS]
    incoming = int(len(df))
    inserted = 0
    skipped = 0
    try:
        if replace_existing:
            for imported_file in df["imported_file"].dropna().astype(str).unique():
                conn.execute("DELETE FROM snapshot_rows WHERE imported_file = ?", (imported_file,))
        for row in df.itertuples(index=False):
            try:
                conn.execute(
                    """
                    INSERT INTO snapshot_rows (
                        source_type, data_date, captured_time, sector_type, sector_name,
                        main_net_inflow_billion, rank_value, change_percent, raw_source,
                        imported_file, imported_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(getattr(row, column) for column in SNAPSHOT_ROW_COLUMNS),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                skipped += 1
        conn.commit()
    except Exception as exc:
        errors.append(str(exc))
    return {
        "incoming_rows": incoming,
        "inserted_rows": inserted,
        "skipped_duplicate_rows": skipped,
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
    }


def _clear_source(conn: sqlite3.Connection, source_type: str) -> None:
    conn.execute("DELETE FROM snapshot_rows WHERE source_type = ?", (source_type,))
    conn.execute("DELETE FROM snapshot_files WHERE source_type = ?", (source_type,))
    conn.commit()


def rebuild_warehouse_from_csv_directory(
    conn: sqlite3.Connection,
    directory: str,
    source_type: str,
    clear_source: bool = False,
) -> dict:
    source = str(source_type or "LOCAL").upper()
    warnings: list[str] = []
    errors: list[str] = []
    imported_files: list[str] = []
    inserted_rows = 0
    skipped_duplicate_rows = 0
    if clear_source:
        _clear_source(conn, source)
    catalog = build_snapshot_file_catalog(directory, pattern="sector_flow_*.csv")
    if catalog.empty:
        return {
            "source_type": source,
            "directory": directory,
            "file_count": 0,
            "imported_file_count": 0,
            "skipped_file_count": 0,
            "inserted_rows": 0,
            "skipped_duplicate_rows": 0,
            "warning_count": 1,
            "error_count": 0,
            "imported_files": [],
            "errors": [],
            "warnings": [f"目录无可导入 CSV：{directory}"],
            "rebuild_label": "无可导入文件",
            "rebuild_reason": "CSV 目录不存在或没有 sector_flow_YYYY-MM-DD.csv 文件。",
        }
    for _, file_row in catalog.iterrows():
        file_path = str(file_row.get("file_path") or "")
        audit = audit_snapshot_csv_file(file_path, source_label=source)
        if audit.get("errors"):
            errors.extend([f"{Path(file_path).name}: {msg}" for msg in audit.get("errors", [])])
            continue
        try:
            raw_df = pd.read_csv(file_path, dtype={"sector_code": str})
        except Exception as exc:
            errors.append(f"{Path(file_path).name}: 读取失败：{exc}")
            continue
        rows = normalize_snapshot_df_for_warehouse(
            raw_df,
            source,
            data_date=file_row.get("data_date"),
            imported_file=file_path,
        )
        write = insert_snapshot_rows(conn, rows)
        inserted_rows += int(write.get("inserted_rows", 0) or 0)
        skipped_duplicate_rows += int(write.get("skipped_duplicate_rows", 0) or 0)
        errors.extend([f"{Path(file_path).name}: {msg}" for msg in write.get("errors", [])])
        warnings.extend([f"{Path(file_path).name}: {msg}" for msg in audit.get("warnings", [])])
        warnings.extend([f"{Path(file_path).name}: {msg}" for msg in write.get("warnings", [])])
        upsert_snapshot_file_record(
            conn,
            {
                "source_type": source,
                "file_path": file_path,
                "file_name": file_row.get("file_name"),
                "data_date": file_row.get("data_date"),
                "file_size_kb": file_row.get("file_size_kb"),
                "row_count": file_row.get("row_count"),
                "captured_time_count": file_row.get("captured_time_count"),
                "quality_label": file_row.get("quality_label"),
                "warning_count": len(audit.get("warnings", [])),
                "error_count": len(audit.get("errors", [])),
            },
        )
        imported_files.append(file_path)
    if errors:
        label = "存在导入问题"
        reason = "部分 CSV 导入失败或存在错误，其他文件已尽量导入。"
    elif imported_files:
        label = "重建完成"
        reason = "CSV 已导入 SQLite warehouse。CSV 仍是主数据来源，warehouse 可随时重建。"
    else:
        label = "无可导入文件"
        reason = "未找到可导入的 CSV 文件。"
    return {
        "source_type": source,
        "directory": directory,
        "file_count": int(len(catalog)),
        "imported_file_count": len(imported_files),
        "skipped_file_count": int(len(catalog) - len(imported_files)),
        "inserted_rows": inserted_rows,
        "skipped_duplicate_rows": skipped_duplicate_rows,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "imported_files": imported_files,
        "errors": errors,
        "warnings": warnings,
        "rebuild_label": label,
        "rebuild_reason": reason,
    }


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
    return row is not None


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def query_warehouse_summary(conn: sqlite3.Connection) -> dict:
    path_row = conn.execute("PRAGMA database_list").fetchone()
    warehouse_path = path_row["file"] if path_row and "file" in path_row.keys() else None
    if not _table_exists(conn, "snapshot_rows") or not _table_exists(conn, "snapshot_files"):
        return {
            "warehouse_path": warehouse_path,
            "snapshot_file_count": 0,
            "snapshot_row_count": 0,
            "local_file_count": 0,
            "sample_file_count": 0,
            "local_row_count": 0,
            "sample_row_count": 0,
            "latest_local_date": None,
            "latest_sample_date": None,
            "captured_time_count": 0,
            "warehouse_label": "warehouse 不存在",
            "warehouse_reason": "SQLite warehouse 尚未初始化。CSV 路径仍可正常运行。",
        }
    local_file_count = int(_scalar(conn, "SELECT COUNT(*) FROM snapshot_files WHERE source_type='LOCAL'") or 0)
    sample_file_count = int(_scalar(conn, "SELECT COUNT(*) FROM snapshot_files WHERE source_type='SAMPLE'") or 0)
    local_row_count = int(_scalar(conn, "SELECT COUNT(*) FROM snapshot_rows WHERE source_type='LOCAL'") or 0)
    sample_row_count = int(_scalar(conn, "SELECT COUNT(*) FROM snapshot_rows WHERE source_type='SAMPLE'") or 0)
    snapshot_file_count = int(_scalar(conn, "SELECT COUNT(*) FROM snapshot_files") or 0)
    snapshot_row_count = int(_scalar(conn, "SELECT COUNT(*) FROM snapshot_rows") or 0)
    if local_row_count:
        label = "warehouse 可用"
        reason = "本地 SQLite warehouse 包含 LOCAL 数据，可作为 CSV 快照的查询索引。"
    elif sample_row_count:
        label = "仅 SAMPLE warehouse 可用"
        reason = "当前 SQLite warehouse 仅包含 SAMPLE 合成样例数据，不代表真实行情。"
    elif snapshot_file_count or snapshot_row_count:
        label = "warehouse 存在问题"
        reason = "SQLite warehouse 存在元数据但缺少可用行，请考虑从 CSV 重建。"
    else:
        label = "warehouse 为空"
        reason = "SQLite warehouse 已初始化但尚未导入 CSV。"
    return {
        "warehouse_path": warehouse_path,
        "snapshot_file_count": snapshot_file_count,
        "snapshot_row_count": snapshot_row_count,
        "local_file_count": local_file_count,
        "sample_file_count": sample_file_count,
        "local_row_count": local_row_count,
        "sample_row_count": sample_row_count,
        "latest_local_date": _scalar(conn, "SELECT MAX(data_date) FROM snapshot_rows WHERE source_type='LOCAL'"),
        "latest_sample_date": _scalar(conn, "SELECT MAX(data_date) FROM snapshot_rows WHERE source_type='SAMPLE'"),
        "captured_time_count": int(_scalar(conn, "SELECT COUNT(DISTINCT captured_time) FROM snapshot_rows") or 0),
        "warehouse_label": label,
        "warehouse_reason": reason,
    }


def query_available_dates(
    conn: sqlite3.Connection,
    source_type: str | None = None,
) -> pd.DataFrame:
    if not _table_exists(conn, "snapshot_rows"):
        return pd.DataFrame(columns=["source_type", "data_date", "row_count", "captured_time_count", "latest_captured_time"])
    params: list[Any] = []
    where = ""
    if source_type:
        where = "WHERE source_type = ?"
        params.append(str(source_type).upper())
    return pd.read_sql_query(
        f"""
        SELECT source_type, data_date, COUNT(*) AS row_count,
               COUNT(DISTINCT captured_time) AS captured_time_count,
               MAX(captured_time) AS latest_captured_time
        FROM snapshot_rows
        {where}
        GROUP BY source_type, data_date
        ORDER BY source_type, data_date DESC
        """,
        conn,
        params=params,
    )


def query_snapshot_rows(
    conn: sqlite3.Connection,
    source_type: str | None = None,
    data_date: str | None = None,
    latest_only: bool = False,
    limit: int | None = None,
) -> pd.DataFrame:
    if not _table_exists(conn, "snapshot_rows"):
        return pd.DataFrame(columns=SNAPSHOT_ROW_COLUMNS)
    clauses = []
    params: list[Any] = []
    if source_type:
        clauses.append("source_type = ?")
        params.append(str(source_type).upper())
    if data_date:
        clauses.append("data_date = ?")
        params.append(data_date)
    if latest_only:
        sub_clauses = list(clauses)
        sub_params = list(params)
        sub_where = "WHERE " + " AND ".join(sub_clauses) if sub_clauses else ""
        latest_time = _scalar(conn, f"SELECT MAX(captured_time) FROM snapshot_rows {sub_where}", tuple(sub_params))
        if latest_time:
            clauses.append("captured_time = ?")
            params.append(latest_time)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    limit_clause = f" LIMIT {int(limit)}" if limit else ""
    return pd.read_sql_query(
        f"""
        SELECT {", ".join(SNAPSHOT_ROW_COLUMNS)}
        FROM snapshot_rows
        {where}
        ORDER BY data_date DESC, captured_time DESC, id ASC
        {limit_clause}
        """,
        conn,
        params=params,
    )


def audit_warehouse(conn: sqlite3.Connection) -> dict:
    required_tables = ("snapshot_files", "snapshot_rows", "warehouse_meta")
    missing_tables = [table for table in required_tables if not _table_exists(conn, table)]
    warnings: list[str] = []
    errors: list[str] = []
    if missing_tables:
        errors.append(f"缺少 warehouse 表：{', '.join(missing_tables)}")
        return {
            "audit_label": "warehouse 未初始化",
            "warning_count": 0,
            "error_count": len(errors),
            "warnings": warnings,
            "errors": errors,
            "duplicate_row_count": 0,
            "empty_sector_name_count": 0,
            "invalid_numeric_count": 0,
        }
    duplicate_row_count = int(
        _scalar(
            conn,
            """
            SELECT COALESCE(SUM(cnt - 1), 0)
            FROM (
                SELECT COUNT(*) AS cnt
                FROM snapshot_rows
                GROUP BY source_type, data_date, captured_time, sector_type, sector_name
                HAVING cnt > 1
            )
            """,
        )
        or 0
    )
    empty_sector_name_count = int(
        _scalar(conn, "SELECT COUNT(*) FROM snapshot_rows WHERE sector_name IS NULL OR TRIM(sector_name) = ''") or 0
    )
    invalid_numeric_count = int(_scalar(conn, "SELECT COUNT(*) FROM snapshot_rows WHERE main_net_inflow_billion IS NULL") or 0)
    empty_imported_file_count = int(
        _scalar(conn, "SELECT COUNT(*) FROM snapshot_rows WHERE imported_file IS NULL OR TRIM(imported_file) = ''") or 0
    )
    if duplicate_row_count:
        warnings.append(f"存在 {duplicate_row_count} 条 source/date/time/sector 重复行。")
    if empty_sector_name_count:
        warnings.append(f"存在 {empty_sector_name_count} 条空 sector_name。")
    if invalid_numeric_count:
        warnings.append(f"存在 {invalid_numeric_count} 条 main_net_inflow_billion 为空。")
    if empty_imported_file_count:
        warnings.append(f"存在 {empty_imported_file_count} 条 imported_file 为空。")
    label = "warehouse 健康" if not warnings and not errors else ("warehouse 存在警告" if not errors else "warehouse 存在错误")
    return {
        "audit_label": label,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
        "duplicate_row_count": duplicate_row_count,
        "empty_sector_name_count": empty_sector_name_count,
        "invalid_numeric_count": invalid_numeric_count,
    }


def summarize_warehouse_status(summary: dict, audit: dict | None = None) -> str:
    audit = audit or {}
    return (
        f"当前本地 SQLite warehouse 状态：{summary.get('warehouse_label', '未知')}。"
        f"包含 {summary.get('local_file_count', 0)} 个 LOCAL CSV 文件和 {summary.get('sample_file_count', 0)} 个 SAMPLE CSV 文件，"
        f"共 {summary.get('snapshot_row_count', 0)} 行索引记录。"
        "CSV 仍是主数据来源，warehouse 是本地可重建查询索引。"
        f"审计状态：{audit.get('audit_label', '未审计')}。"
    )


def validate_warehouse_text(text: str) -> list[str]:
    hits = []
    for word in FORBIDDEN_WAREHOUSE_WORDS:
        if word in (text or ""):
            hits.append(word)
    return sorted(set(hits), key=hits.index)
