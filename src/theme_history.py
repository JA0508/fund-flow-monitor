from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from src.theme_pool import build_theme_snapshot
from src.theme_taxonomy import get_taxonomy_themes
from src.warehouse_explorer import get_warehouse_available_source_types


MODE_LABEL_TO_VALUE = {
    "严格代表口径": "strict_representative",
    "代表口径": "representative",
    "广度观察": "breadth",
}
DEFAULT_THEME_HISTORY_MODE = "代表口径"
FORBIDDEN_THEME_HISTORY_WORDS = (
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
    "趋势确立",
    "反转确认",
)
SECTOR_HISTORY_COLUMNS = [
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
THEME_HISTORY_COLUMNS = [
    "source_type",
    "data_date",
    "captured_time",
    "theme_name",
    "theme_group",
    "main_net_inflow_billion",
    "theme_status",
    "theme_status_level",
    "match_strategy",
    "source_count",
    "positive_source_count",
    "negative_source_count",
    "neutral_source_count",
    "theme_mode",
    "data_status_label",
]


def get_theme_history_mode_options() -> list[str]:
    return list(MODE_LABEL_TO_VALUE.keys())


def normalize_theme_history_mode(mode: str | None) -> str:
    if mode in MODE_LABEL_TO_VALUE:
        return str(mode)
    if mode in MODE_LABEL_TO_VALUE.values():
        reverse = {value: label for label, value in MODE_LABEL_TO_VALUE.items()}
        return reverse.get(str(mode), DEFAULT_THEME_HISTORY_MODE)
    return DEFAULT_THEME_HISTORY_MODE


def _mode_value(mode: str | None) -> str:
    return MODE_LABEL_TO_VALUE[normalize_theme_history_mode(mode)]


def _table_exists(conn: sqlite3.Connection | None, table_name: str) -> bool:
    if conn is None:
        return False
    try:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
        return row is not None
    except Exception:
        return False


def load_sector_history_from_warehouse(
    conn,
    source_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    latest_per_day: bool = True,
    limit_days: int | None = 60,
) -> pd.DataFrame:
    if conn is None or not _table_exists(conn, "snapshot_rows"):
        return pd.DataFrame(columns=SECTOR_HISTORY_COLUMNS)
    clauses: list[str] = []
    params: list[Any] = []
    source = str(source_type or "ALL").upper()
    if source and source != "ALL":
        clauses.append("source_type = ?")
        params.append(source)
    if start_date:
        clauses.append("data_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("data_date <= ?")
        params.append(end_date)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    try:
        date_sql = f"SELECT DISTINCT data_date FROM snapshot_rows {where} ORDER BY data_date DESC"
        if limit_days:
            date_sql += f" LIMIT {max(1, min(int(limit_days), 365))}"
        date_rows = conn.execute(date_sql, tuple(params)).fetchall()
        dates = [str(row[0]) for row in date_rows if row[0]]
        if not dates:
            return pd.DataFrame(columns=SECTOR_HISTORY_COLUMNS)
        date_placeholders = ",".join("?" for _ in dates)
        row_clauses = list(clauses) + [f"data_date IN ({date_placeholders})"]
        row_params = list(params) + dates
        row_where = "WHERE " + " AND ".join(row_clauses)
        df = pd.read_sql_query(
            f"""
            SELECT source_type, data_date, captured_time, sector_type, sector_name,
                   main_net_inflow_billion, rank_value, change_percent, imported_file
            FROM snapshot_rows
            {row_where}
            ORDER BY source_type, data_date, captured_time, sector_name
            """,
            conn,
            params=row_params,
        )
    except Exception:
        return pd.DataFrame(columns=SECTOR_HISTORY_COLUMNS)
    if df.empty:
        return pd.DataFrame(columns=SECTOR_HISTORY_COLUMNS)
    df["main_net_inflow_billion"] = pd.to_numeric(df["main_net_inflow_billion"], errors="coerce")
    if latest_per_day:
        latest = df.groupby(["source_type", "data_date"])["captured_time"].transform("max")
        df = df[df["captured_time"].eq(latest)].copy()
    return df[SECTOR_HISTORY_COLUMNS].reset_index(drop=True)


def _theme_group_map(taxonomy: dict) -> dict[str, str]:
    return {str(theme.get("theme_name", "")).strip(): str(theme.get("theme_group", "")).strip() for theme in get_taxonomy_themes(taxonomy)}


def _source_counts(sectors: str | None, source_df: pd.DataFrame) -> tuple[int, int, int]:
    if not sectors:
        return 0, 0, 0
    names = [item for item in str(sectors).split("，") if item]
    matched = source_df[source_df["sector_name"].astype(str).isin(names)].copy()
    values = pd.to_numeric(matched["main_net_inflow_billion"], errors="coerce")
    return int(values.gt(5).sum()), int(values.lt(-5).sum()), int(values.between(-5, 5, inclusive="both").sum())


def _data_status_label(source_type: str) -> str:
    source = str(source_type or "").upper()
    if source == "SAMPLE":
        return "SAMPLE 合成演示数据，不代表真实行情"
    if source == "LOCAL":
        return "LOCAL 本地真实缓存索引"
    return f"{source or 'UNKNOWN'} warehouse 历史索引"


def build_theme_history_from_sector_history(
    sector_history_df: pd.DataFrame,
    taxonomy: dict,
    theme_mode: str = DEFAULT_THEME_HISTORY_MODE,
) -> pd.DataFrame:
    if sector_history_df is None or sector_history_df.empty:
        return pd.DataFrame(columns=THEME_HISTORY_COLUMNS)
    df = sector_history_df.copy()
    required = {"source_type", "data_date", "captured_time", "sector_name", "main_net_inflow_billion"}
    if not required.issubset(df.columns):
        return pd.DataFrame(columns=THEME_HISTORY_COLUMNS)
    df["main_net_inflow_billion"] = pd.to_numeric(df["main_net_inflow_billion"], errors="coerce")
    df = df.dropna(subset=["source_type", "data_date", "captured_time", "sector_name", "main_net_inflow_billion"])
    if df.empty:
        return pd.DataFrame(columns=THEME_HISTORY_COLUMNS)
    mode_label = normalize_theme_history_mode(theme_mode)
    mode_value = _mode_value(mode_label)
    groups = _theme_group_map(taxonomy)
    rows: list[dict] = []
    for (source, data_date, captured_time), frame in df.groupby(["source_type", "data_date", "captured_time"], sort=True):
        snapshot = build_theme_snapshot(frame, theme_mode=mode_value)
        if snapshot.empty:
            continue
        for _, row in snapshot.iterrows():
            positive, negative, neutral = _source_counts(row.get("source_sectors"), frame)
            rows.append(
                {
                    "source_type": source,
                    "data_date": data_date,
                    "captured_time": captured_time,
                    "theme_name": row.get("theme_name"),
                    "theme_group": groups.get(str(row.get("theme_name")), ""),
                    "main_net_inflow_billion": row.get("main_net_inflow_billion"),
                    "theme_status": row.get("theme_status"),
                    "theme_status_level": row.get("theme_status_level"),
                    "match_strategy": row.get("match_strategy"),
                    "source_count": row.get("source_sector_count"),
                    "positive_source_count": positive,
                    "negative_source_count": negative,
                    "neutral_source_count": neutral,
                    "theme_mode": mode_label,
                    "data_status_label": _data_status_label(str(source)),
                }
            )
    if not rows:
        return pd.DataFrame(columns=THEME_HISTORY_COLUMNS)
    out = pd.DataFrame(rows)
    out["main_net_inflow_billion"] = pd.to_numeric(out["main_net_inflow_billion"], errors="coerce")
    return out[THEME_HISTORY_COLUMNS].sort_values(["source_type", "data_date", "theme_name"]).reset_index(drop=True)


def build_theme_history_matrix(
    theme_history_df: pd.DataFrame,
    value_column: str = "main_net_inflow_billion",
) -> pd.DataFrame:
    if theme_history_df is None or theme_history_df.empty or value_column not in theme_history_df.columns:
        return pd.DataFrame()
    df = theme_history_df.copy()
    df[value_column] = pd.to_numeric(df[value_column], errors="coerce")
    matrix = df.pivot_table(index="data_date", columns="theme_name", values=value_column, aggfunc="last")
    return matrix.sort_index().reset_index()


def _status_change(first: pd.Series | None, current: pd.Series, previous: pd.Series | None) -> tuple[str, str]:
    if previous is None:
        return "样本不足", "当前主题只有一个历史样本，暂不判断状态变化。"
    prev_value = float(previous.get("main_net_inflow_billion", 0) or 0)
    curr_value = float(current.get("main_net_inflow_billion", 0) or 0)
    prev_positive = prev_value > 5
    curr_positive = curr_value > 5
    prev_negative = prev_value < -5
    curr_negative = curr_value < -5
    if prev_positive and curr_positive:
        return "延续偏强", "该主题在相邻历史样本中维持净流入状态。"
    if prev_negative and curr_negative:
        return "延续承压", "该主题在相邻历史样本中维持净流出状态。"
    if prev_negative and curr_positive:
        return "由弱转强", "该主题从历史净流出转为当前净流入，属于已发生的资金状态变化。"
    if prev_positive and curr_negative:
        return "由强转弱", "该主题从历史净流入转为当前净流出，属于已发生的资金状态变化。"
    return "分化震荡", "该主题历史样本中的资金状态分化，当前仅作观察。"


def build_theme_status_timeline(theme_history_df: pd.DataFrame) -> pd.DataFrame:
    if theme_history_df is None or theme_history_df.empty:
        return pd.DataFrame(
            columns=[
                "source_type",
                "theme_name",
                "theme_group",
                "data_date",
                "captured_time",
                "theme_status",
                "main_net_inflow_billion",
                "status_change_label",
                "status_change_reason",
            ]
        )
    rows = []
    df = theme_history_df.sort_values(["source_type", "theme_name", "data_date", "captured_time"]).copy()
    for (_, theme_name), group in df.groupby(["source_type", "theme_name"], sort=False):
        previous = None
        first = group.iloc[0] if not group.empty else None
        for _, current in group.iterrows():
            label, reason = _status_change(first, current, previous)
            rows.append(
                {
                    "source_type": current.get("source_type"),
                    "theme_name": theme_name,
                    "theme_group": current.get("theme_group"),
                    "data_date": current.get("data_date"),
                    "captured_time": current.get("captured_time"),
                    "theme_status": current.get("theme_status"),
                    "main_net_inflow_billion": current.get("main_net_inflow_billion"),
                    "status_change_label": label,
                    "status_change_reason": reason,
                }
            )
            previous = current
    return pd.DataFrame(rows).reset_index(drop=True)


def summarize_theme_history(theme_history_df: pd.DataFrame, top_n: int = 5) -> dict:
    warnings: list[str] = []
    errors: list[str] = []
    if theme_history_df is None or theme_history_df.empty:
        return {
            "history_available": False,
            "source_type_count": 0,
            "date_count": 0,
            "theme_count": 0,
            "latest_date": None,
            "strongest_latest_themes": [],
            "pressured_latest_themes": [],
            "most_consistent_positive_themes": [],
            "most_consistent_pressure_themes": [],
            "high_variation_themes": [],
            "summary_label": "暂无主题历史数据",
            "summary_reason": "当前 warehouse 中没有可聚合的主题历史数据。CSV 路径仍可正常使用。",
            "warnings": warnings,
            "errors": errors,
        }
    df = theme_history_df.copy()
    df["main_net_inflow_billion"] = pd.to_numeric(df["main_net_inflow_billion"], errors="coerce")
    latest_date = str(df["data_date"].dropna().max())
    latest = df[df["data_date"].astype(str).eq(latest_date)].copy()
    top_n = max(1, int(top_n or 5))
    strongest = latest.sort_values("main_net_inflow_billion", ascending=False)["theme_name"].head(top_n).dropna().astype(str).tolist()
    pressured = latest.sort_values("main_net_inflow_billion", ascending=True)["theme_name"].head(top_n).dropna().astype(str).tolist()
    grouped = df.groupby("theme_name")["main_net_inflow_billion"]
    positive_ratio = grouped.apply(lambda values: pd.to_numeric(values, errors="coerce").gt(5).mean()).sort_values(ascending=False)
    pressure_ratio = grouped.apply(lambda values: pd.to_numeric(values, errors="coerce").lt(-5).mean()).sort_values(ascending=False)
    variation = grouped.std().fillna(0).sort_values(ascending=False)
    source_types = set(df["source_type"].dropna().astype(str).str.upper())
    date_count = int(df["data_date"].nunique())
    if source_types == {"SAMPLE"}:
        label = "仅 SAMPLE 主题历史可用"
        reason = "当前 warehouse 中仅包含 SAMPLE 合成演示数据，可用于展示主题历史聚合流程，不代表真实行情。"
    elif date_count < 2:
        label = "主题历史样本较少"
        reason = "当前主题历史日期数量较少，仅适合查看单点或少量样本状态。"
    else:
        label = "主题历史样本充足"
        reason = "当前 warehouse 中存在多个历史日期，可用于只读观察主题资金状态变化。"
    return {
        "history_available": True,
        "source_type_count": int(df["source_type"].nunique()),
        "date_count": date_count,
        "theme_count": int(df["theme_name"].nunique()),
        "latest_date": latest_date,
        "strongest_latest_themes": strongest,
        "pressured_latest_themes": pressured,
        "most_consistent_positive_themes": positive_ratio.head(top_n).index.astype(str).tolist(),
        "most_consistent_pressure_themes": pressure_ratio.head(top_n).index.astype(str).tolist(),
        "high_variation_themes": variation.head(top_n).index.astype(str).tolist(),
        "summary_label": label,
        "summary_reason": reason,
        "warnings": warnings,
        "errors": errors,
    }


def build_theme_history_quality_report(
    sector_history_df: pd.DataFrame,
    theme_history_df: pd.DataFrame,
) -> dict:
    warnings: list[str] = []
    errors: list[str] = []
    if sector_history_df is None or sector_history_df.empty:
        warnings.append("sector_history 为空。")
    if theme_history_df is None or theme_history_df.empty:
        warnings.append("theme_history 为空。")
        return {
            "quality_label": "暂无主题历史数据",
            "warning_count": len(warnings),
            "error_count": len(errors),
            "warnings": warnings,
            "errors": errors,
            "date_count": 0,
            "theme_count": 0,
            "row_count": 0,
            "duplicate_theme_date_count": 0,
        }
    df = theme_history_df.copy()
    df["main_net_inflow_billion"] = pd.to_numeric(df["main_net_inflow_billion"], errors="coerce")
    missing_theme = int(df["theme_name"].isna().sum())
    invalid_numeric = int(df["main_net_inflow_billion"].isna().sum())
    duplicate_count = int(
        df.duplicated(subset=["source_type", "data_date", "captured_time", "theme_name"], keep=False).sum()
    )
    if missing_theme:
        errors.append(f"存在 {missing_theme} 条缺失 theme_name。")
    if invalid_numeric:
        warnings.append(f"存在 {invalid_numeric} 条主题资金数值为空。")
    if duplicate_count:
        warnings.append(f"存在 {duplicate_count} 条重复 source/date/time/theme 记录。")
    source_types = set(df["source_type"].dropna().astype(str).str.upper())
    if "SAMPLE" in source_types and "LOCAL" in source_types and "data_status_label" not in df.columns:
        warnings.append("同时存在 SAMPLE / LOCAL，但缺少 data_status_label 标注。")
    label = "主题历史质量良好" if not warnings and not errors else ("主题历史存在警告" if not errors else "主题历史存在错误")
    return {
        "quality_label": label,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
        "date_count": int(df["data_date"].nunique()),
        "theme_count": int(df["theme_name"].nunique()),
        "row_count": int(len(df)),
        "duplicate_theme_date_count": duplicate_count,
    }


def summarize_theme_history_quality(report: dict) -> str:
    return (
        f"主题历史聚合质量：{report.get('quality_label', '未知')}。"
        f"覆盖 {report.get('date_count', 0)} 个日期、{report.get('theme_count', 0)} 个主题、{report.get('row_count', 0)} 条主题记录。"
        "CSV 仍是主数据来源，warehouse 只是可重建索引；主题历史只描述已保存的历史资金状态。"
    )


def validate_theme_history_text(text: str) -> list[str]:
    return [word for word in FORBIDDEN_THEME_HISTORY_WORDS if word in str(text or "")]


def get_available_source_types_for_theme_history(conn) -> list[str]:
    return get_warehouse_available_source_types(conn)
