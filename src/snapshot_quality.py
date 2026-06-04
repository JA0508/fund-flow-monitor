from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


FORBIDDEN_WORDS = (
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

SNAPSHOT_FILE_PATTERN = re.compile(r"sector_flow_(\d{4}-\d{2}-\d{2})\.csv$")


def get_snapshot_required_columns() -> list[str]:
    return ["sector_name", "main_net_inflow_billion", "captured_time"]


def normalize_snapshot_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    work = df.copy()
    work.columns = [str(column).strip() for column in work.columns]
    alias_map = {
        "sector_name": ("sector_name", "板块名称", "行业名称", "概念名称", "name", "名称"),
        "main_net_inflow_billion": ("main_net_inflow_billion", "主力净流入亿元", "主力净流入_亿元"),
        "main_net_inflow_yuan": ("main_net_inflow_yuan", "主力净流入-净额", "主力净流入净额"),
        "captured_time": ("captured_time", "采集时间", "时间"),
        "captured_at": ("captured_at", "采集时间戳"),
        "sector_type": ("sector_type", "板块类型"),
    }
    for target, aliases in alias_map.items():
        if target in work.columns:
            continue
        for alias in aliases:
            if alias in work.columns:
                work[target] = work[alias]
                break
    if "main_net_inflow_billion" not in work.columns and "main_net_inflow_yuan" in work.columns:
        yuan = pd.to_numeric(work["main_net_inflow_yuan"], errors="coerce")
        work["main_net_inflow_billion"] = yuan / 100_000_000
    if "captured_time" not in work.columns and "captured_at" in work.columns:
        captured = pd.to_datetime(work["captured_at"], errors="coerce")
        work["captured_time"] = captured.dt.strftime("%H:%M:%S")
    if "main_net_inflow_billion" in work.columns:
        work["main_net_inflow_billion"] = pd.to_numeric(work["main_net_inflow_billion"], errors="coerce")
    if "sector_name" in work.columns:
        work["sector_name"] = work["sector_name"].astype("string").str.strip()
    if "captured_time" in work.columns:
        work["captured_time"] = work["captured_time"].astype("string").str.strip()
    return work


def _latest_non_null(series: pd.Series) -> str | None:
    values = series.dropna().astype(str)
    if values.empty:
        return None
    return str(values.iloc[-1])


def _quality_from_findings(
    row_count: int,
    missing_required_columns: list[str],
    invalid_numeric_count: int,
    duplicate_row_count: int,
    empty_sector_name_count: int,
    read_errors: list[str] | None = None,
) -> tuple[str, int]:
    if row_count <= 0:
        return "无可用数据", 0
    score = 100
    if read_errors:
        score -= 60
    score -= min(60, len(missing_required_columns) * 25)
    if invalid_numeric_count:
        score -= min(25, 5 + invalid_numeric_count)
    if duplicate_row_count:
        score -= min(20, 5 + duplicate_row_count)
    if empty_sector_name_count:
        score -= min(20, 5 + empty_sector_name_count)
    score = max(0, min(100, score))
    if missing_required_columns or read_errors or score < 60:
        return "存在明显问题", score
    if invalid_numeric_count or duplicate_row_count or empty_sector_name_count or score < 90:
        return "存在轻微警告", score
    return "数据质量良好", score


def audit_snapshot_dataframe(
    df: pd.DataFrame,
    source_label: str = "unknown",
    file_path: str | None = None,
) -> dict:
    raw_df = pd.DataFrame() if df is None else df.copy()
    normalized = normalize_snapshot_columns(raw_df)
    required_columns = get_snapshot_required_columns()
    missing_required_columns = [column for column in required_columns if column not in normalized.columns]
    warnings: list[str] = []
    errors: list[str] = []
    if normalized.empty:
        warnings.append("DataFrame 为空，暂无可审计记录。")
    for column in missing_required_columns:
        errors.append(f"缺少必需字段：{column}")

    captured_time_count = int(normalized["captured_time"].nunique()) if "captured_time" in normalized.columns else 0
    latest_captured_time = _latest_non_null(normalized["captured_time"]) if "captured_time" in normalized.columns else None
    earliest_captured_time = (
        str(normalized["captured_time"].dropna().astype(str).sort_values().iloc[0])
        if "captured_time" in normalized.columns and not normalized["captured_time"].dropna().empty
        else None
    )
    invalid_numeric_count = 0
    if "main_net_inflow_billion" in normalized.columns:
        invalid_numeric_count = int(pd.to_numeric(normalized["main_net_inflow_billion"], errors="coerce").isna().sum())
        if invalid_numeric_count:
            warnings.append(f"main_net_inflow_billion 存在 {invalid_numeric_count} 个无法解析的数值。")
    empty_sector_name_count = 0
    if "sector_name" in normalized.columns:
        empty_sector_name_count = int(normalized["sector_name"].fillna("").astype(str).str.strip().eq("").sum())
        if empty_sector_name_count:
            warnings.append(f"sector_name 存在 {empty_sector_name_count} 个空值。")

    duplicate_df = detect_duplicate_captured_times(normalized)
    duplicate_row_count = int(duplicate_df["duplicate_count"].sub(1).sum()) if not duplicate_df.empty and "duplicate_count" in duplicate_df.columns else 0
    duplicate_captured_time_count = int(duplicate_df["captured_time"].nunique()) if not duplicate_df.empty and "captured_time" in duplicate_df.columns else 0
    if duplicate_row_count:
        warnings.append(f"检测到 {duplicate_row_count} 条 captured_time + sector_name 重复追加记录。")

    null_counts = {
        column: int(normalized[column].isna().sum())
        for column in normalized.columns
        if normalized[column].isna().any()
    }
    quality_label, quality_score = _quality_from_findings(
        row_count=len(normalized),
        missing_required_columns=missing_required_columns,
        invalid_numeric_count=invalid_numeric_count,
        duplicate_row_count=duplicate_row_count,
        empty_sector_name_count=empty_sector_name_count,
    )
    if quality_label == "数据质量良好":
        warnings = warnings
    return {
        "source_label": source_label,
        "file_path": file_path,
        "row_count": int(len(normalized)),
        "column_count": int(len(normalized.columns)),
        "captured_time_count": captured_time_count,
        "latest_captured_time": latest_captured_time,
        "earliest_captured_time": earliest_captured_time,
        "duplicate_row_count": duplicate_row_count,
        "duplicate_captured_time_count": duplicate_captured_time_count,
        "missing_required_columns": missing_required_columns,
        "null_counts": null_counts,
        "invalid_numeric_count": invalid_numeric_count,
        "empty_sector_name_count": empty_sector_name_count,
        "quality_label": quality_label,
        "quality_score": quality_score,
        "warnings": warnings,
        "errors": errors,
    }


def audit_snapshot_csv_file(path: str, source_label: str = "local") -> dict:
    file_path = Path(path)
    if not file_path.exists():
        return {
            "source_label": source_label,
            "file_path": str(file_path),
            "row_count": 0,
            "column_count": 0,
            "captured_time_count": 0,
            "latest_captured_time": None,
            "earliest_captured_time": None,
            "duplicate_row_count": 0,
            "duplicate_captured_time_count": 0,
            "missing_required_columns": get_snapshot_required_columns(),
            "null_counts": {},
            "invalid_numeric_count": 0,
            "empty_sector_name_count": 0,
            "quality_label": "无可用数据",
            "quality_score": 0,
            "warnings": [],
            "errors": [f"文件不存在：{file_path}"],
        }
    try:
        df = pd.read_csv(file_path, dtype={"sector_code": str})
    except Exception as exc:
        return {
            "source_label": source_label,
            "file_path": str(file_path),
            "row_count": 0,
            "column_count": 0,
            "captured_time_count": 0,
            "latest_captured_time": None,
            "earliest_captured_time": None,
            "duplicate_row_count": 0,
            "duplicate_captured_time_count": 0,
            "missing_required_columns": get_snapshot_required_columns(),
            "null_counts": {},
            "invalid_numeric_count": 0,
            "empty_sector_name_count": 0,
            "quality_label": "存在明显问题",
            "quality_score": 0,
            "warnings": [],
            "errors": [f"CSV 文件不可读或解析失败：{exc}"],
        }
    return audit_snapshot_dataframe(df, source_label=source_label, file_path=str(file_path))


def _parse_data_date(path: Path) -> str | None:
    match = SNAPSHOT_FILE_PATTERN.search(path.name)
    return match.group(1) if match else None


def build_snapshot_file_catalog(directory: str = "data/ticks", pattern: str = "*.csv") -> pd.DataFrame:
    root = Path(directory)
    columns = [
        "file_path",
        "file_name",
        "data_date",
        "file_size_kb",
        "modified_time",
        "row_count",
        "captured_time_count",
        "latest_captured_time",
        "quality_label",
        "warning_count",
        "error_count",
    ]
    if not root.exists():
        return pd.DataFrame(columns=columns)
    rows = []
    for path in sorted(root.glob(pattern)):
        audit = audit_snapshot_csv_file(str(path), source_label=str(directory))
        rows.append(
            {
                "file_path": str(path),
                "file_name": path.name,
                "data_date": _parse_data_date(path),
                "file_size_kb": round(path.stat().st_size / 1024, 1) if path.exists() else 0,
                "modified_time": pd.Timestamp(path.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S") if path.exists() else None,
                "row_count": int(audit.get("row_count", 0) or 0),
                "captured_time_count": int(audit.get("captured_time_count", 0) or 0),
                "latest_captured_time": audit.get("latest_captured_time"),
                "quality_label": audit.get("quality_label", "--"),
                "warning_count": len(audit.get("warnings") or []),
                "error_count": len(audit.get("errors") or []),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _overall_quality_label(file_count: int, warning_count: int, error_count: int) -> str:
    if file_count <= 0:
        return "暂无真实缓存"
    if error_count:
        return "存在坏 CSV"
    if warning_count:
        return "存在轻微警告"
    return "数据质量良好"


def build_snapshot_quality_report(
    directory: str = "data/ticks",
    sample_directory: str = "sample_data/ticks",
) -> dict:
    local_catalog_df = build_snapshot_file_catalog(directory)
    sample_catalog_df = build_snapshot_file_catalog(sample_directory)
    local_warning_count = int(local_catalog_df["warning_count"].sum()) if not local_catalog_df.empty else 0
    local_error_count = int(local_catalog_df["error_count"].sum()) if not local_catalog_df.empty else 0
    sample_warning_count = int(sample_catalog_df["warning_count"].sum()) if not sample_catalog_df.empty else 0
    sample_error_count = int(sample_catalog_df["error_count"].sum()) if not sample_catalog_df.empty else 0
    local_file_count = int(len(local_catalog_df))
    sample_file_count = int(len(sample_catalog_df))
    local_quality_label = _overall_quality_label(local_file_count, local_warning_count, local_error_count)
    sample_quality_label = _overall_quality_label(sample_file_count, sample_warning_count, sample_error_count)
    local_total_rows = int(local_catalog_df["row_count"].sum()) if not local_catalog_df.empty else 0
    sample_total_rows = int(sample_catalog_df["row_count"].sum()) if not sample_catalog_df.empty else 0
    local_latest_date = (
        str(local_catalog_df["data_date"].dropna().sort_values().iloc[-1])
        if not local_catalog_df.empty and not local_catalog_df["data_date"].dropna().empty
        else None
    )
    sample_latest_date = (
        str(sample_catalog_df["data_date"].dropna().sort_values().iloc[-1])
        if not sample_catalog_df.empty and not sample_catalog_df["data_date"].dropna().empty
        else None
    )
    if local_error_count or sample_error_count:
        report_label = "存在坏 CSV"
    elif local_file_count:
        report_label = "本地缓存可用"
    elif sample_file_count:
        report_label = "仅 SAMPLE 可用"
    else:
        report_label = "无可用快照"
    report_reason = summarize_snapshot_quality(
        {
            "local_file_count": local_file_count,
            "sample_file_count": sample_file_count,
            "local_total_rows": local_total_rows,
            "sample_total_rows": sample_total_rows,
            "local_latest_date": local_latest_date,
            "sample_latest_date": sample_latest_date,
            "local_quality_label": local_quality_label,
            "sample_quality_label": sample_quality_label,
            "local_warning_count": local_warning_count,
            "local_error_count": local_error_count,
            "sample_warning_count": sample_warning_count,
            "sample_error_count": sample_error_count,
            "report_label": report_label,
        }
    )
    return {
        "local_catalog_df": local_catalog_df,
        "sample_catalog_df": sample_catalog_df,
        "local_file_count": local_file_count,
        "sample_file_count": sample_file_count,
        "local_total_rows": local_total_rows,
        "sample_total_rows": sample_total_rows,
        "local_latest_date": local_latest_date,
        "sample_latest_date": sample_latest_date,
        "local_quality_label": local_quality_label,
        "sample_quality_label": sample_quality_label,
        "local_warning_count": local_warning_count,
        "local_error_count": local_error_count,
        "sample_warning_count": sample_warning_count,
        "sample_error_count": sample_error_count,
        "report_label": report_label,
        "report_reason": report_reason,
    }


def detect_duplicate_captured_times(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["captured_time", "sector_name", "duplicate_count", "unique_sector_count", "duplicate_reason"])
    work = normalize_snapshot_columns(df)
    if "captured_time" not in work.columns or "sector_name" not in work.columns:
        return pd.DataFrame(columns=["captured_time", "sector_name", "duplicate_count", "unique_sector_count", "duplicate_reason"])
    group_cols = ["captured_time", "sector_name"]
    if "sector_type" in work.columns:
        group_cols = ["captured_time", "sector_type", "sector_name"]
    counts = work.groupby(group_cols, dropna=False).size().reset_index(name="duplicate_count")
    duplicates = counts[counts["duplicate_count"].gt(1)].copy()
    if duplicates.empty:
        return pd.DataFrame(columns=["captured_time", "sector_name", "duplicate_count", "unique_sector_count", "duplicate_reason"])
    unique_counts = work.groupby("captured_time")["sector_name"].nunique(dropna=True).reset_index(name="unique_sector_count")
    duplicates = duplicates.merge(unique_counts, on="captured_time", how="left")
    duplicates["duplicate_reason"] = "同一 captured_time + sector_name 出现多次，可能是重复追加。"
    preferred = ["captured_time", "sector_name", "duplicate_count", "unique_sector_count", "duplicate_reason"]
    extra = [column for column in duplicates.columns if column not in preferred]
    return duplicates[preferred + extra].reset_index(drop=True)


def summarize_snapshot_quality(report: dict) -> str:
    local_file_count = int(report.get("local_file_count", 0) or 0)
    sample_file_count = int(report.get("sample_file_count", 0) or 0)
    local_latest_date = report.get("local_latest_date") or "暂无"
    sample_latest_date = report.get("sample_latest_date") or "暂无"
    local_warning_count = int(report.get("local_warning_count", 0) or 0)
    local_error_count = int(report.get("local_error_count", 0) or 0)
    sample_warning_count = int(report.get("sample_warning_count", 0) or 0)
    sample_error_count = int(report.get("sample_error_count", 0) or 0)
    if local_file_count:
        local_part = (
            f"当前本地真实缓存包含 {local_file_count} 个 CSV 文件，最新日期为 {local_latest_date}，"
            f"warning/error 为 {local_warning_count}/{local_error_count}。"
        )
    else:
        local_part = "当前暂无本地真实 CSV 缓存。"
    if sample_file_count:
        sample_part = (
            f"SAMPLE 样例目录包含 {sample_file_count} 个 CSV 文件，最新样例日期为 {sample_latest_date}，"
            f"warning/error 为 {sample_warning_count}/{sample_error_count}。SAMPLE 数据仅用于公开演示，不代表真实行情。"
        )
    else:
        sample_part = "SAMPLE 样例目录暂无可用 CSV。"
    if local_error_count or sample_error_count:
        tail = "当前存在不可读或字段异常的 CSV，页面会跳过异常文件并展示可读数据。"
    elif local_file_count:
        tail = "整体可用于历史回放和主题观察。"
    elif sample_file_count:
        tail = "可以切换到 SAMPLE 模式体验完整页面。"
    else:
        tail = "可以等待实时抓取成功，或运行样例数据生成脚本。"
    return local_part + sample_part + tail


def validate_snapshot_quality_text(text: str) -> list[str]:
    content = str(text or "")
    return [word for word in FORBIDDEN_WORDS if word in content]
