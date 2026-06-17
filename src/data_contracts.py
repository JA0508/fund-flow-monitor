from __future__ import annotations

from pathlib import Path

import pandas as pd


SNAPSHOT_REQUIRED_COLUMNS = (
    "captured_time",
    "sector_type",
    "sector_name",
    "main_net_inflow_billion",
)

SNAPSHOT_RECOMMENDED_COLUMNS = (
    "trade_date",
    "captured_at",
    "sector_code",
    "change_pct",
    "main_net_inflow_yuan",
    "source",
)

SAMPLE_REQUIRED_COLUMNS = SNAPSHOT_REQUIRED_COLUMNS + ("source", "data_mode")

NUMERIC_SNAPSHOT_COLUMNS = (
    "change_pct",
    "main_net_inflow_yuan",
    "main_net_inflow_billion",
    "main_net_ratio",
    "super_large_net_inflow_yuan",
    "large_net_inflow_yuan",
    "medium_net_inflow_yuan",
    "small_net_inflow_yuan",
)

FORBIDDEN_CONTRACT_WORDS = (
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
    "强烈看好",
    "明确机会",
    "建议关注",
)


def _empty_report(contract_name: str, context: str) -> dict:
    return {
        "contract_name": contract_name,
        "context": context,
        "contract_ok": False,
        "contract_label": "数据为空",
        "row_count": 0,
        "column_count": 0,
        "missing_required_columns": [],
        "missing_recommended_columns": [],
        "empty_required_columns": [],
        "invalid_numeric_columns": [],
        "sample_marker_ok": False,
        "industry_row_count": 0,
        "concept_row_count": 0,
        "warning_count": 0,
        "error_count": 1,
        "warnings": [],
        "errors": ["DataFrame 为空，无法验证资金流快照结构。"],
    }


def validate_snapshot_dataframe(
    df: pd.DataFrame | None,
    context: str = "snapshot",
    required_columns: tuple[str, ...] = SNAPSHOT_REQUIRED_COLUMNS,
    recommended_columns: tuple[str, ...] = SNAPSHOT_RECOMMENDED_COLUMNS,
) -> dict:
    if df is None or df.empty:
        return _empty_report("snapshot", context)

    warnings: list[str] = []
    errors: list[str] = []
    columns = set(map(str, df.columns))
    missing_required = [column for column in required_columns if column not in columns]
    missing_recommended = [column for column in recommended_columns if column not in columns]
    if missing_required:
        errors.append(f"缺少必要列：{', '.join(missing_required)}")
    if missing_recommended:
        warnings.append(f"缺少推荐列：{', '.join(missing_recommended)}")

    empty_required: list[str] = []
    for column in required_columns:
        if column not in df.columns:
            continue
        series = df[column]
        empty_mask = series.isna() | series.astype(str).str.strip().eq("")
        if bool(empty_mask.any()):
            empty_required.append(column)
    if empty_required:
        errors.append(f"必要列存在空值：{', '.join(empty_required)}")

    invalid_numeric: list[str] = []
    for column in NUMERIC_SNAPSHOT_COLUMNS:
        if column not in df.columns:
            continue
        converted = pd.to_numeric(df[column], errors="coerce")
        invalid_mask = df[column].notna() & converted.isna()
        if bool(invalid_mask.any()):
            invalid_numeric.append(column)
    if invalid_numeric:
        errors.append(f"数值列存在不可解析值：{', '.join(invalid_numeric)}")

    industry_rows = 0
    concept_rows = 0
    if "sector_type" in df.columns:
        sector_type = df["sector_type"].astype(str)
        industry_rows = int(sector_type.eq("行业资金流").sum())
        concept_rows = int(sector_type.eq("概念资金流").sum())
        if industry_rows == 0:
            warnings.append("缺少 行业资金流 行，主题主链路可能无法构建。")

    error_count = len(errors)
    warning_count = len(warnings)
    if error_count:
        label = "数据契约不通过"
    elif warning_count:
        label = "数据契约通过但有警告"
    else:
        label = "数据契约通过"
    return {
        "contract_name": "snapshot",
        "context": context,
        "contract_ok": error_count == 0,
        "contract_label": label,
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "missing_required_columns": missing_required,
        "missing_recommended_columns": missing_recommended,
        "empty_required_columns": empty_required,
        "invalid_numeric_columns": invalid_numeric,
        "sample_marker_ok": False,
        "industry_row_count": industry_rows,
        "concept_row_count": concept_rows,
        "warning_count": warning_count,
        "error_count": error_count,
        "warnings": warnings,
        "errors": errors,
    }


def validate_sample_snapshot_dataframe(df: pd.DataFrame | None, context: str = "sample_snapshot") -> dict:
    report = validate_snapshot_dataframe(
        df,
        context=context,
        required_columns=SAMPLE_REQUIRED_COLUMNS,
        recommended_columns=SNAPSHOT_RECOMMENDED_COLUMNS,
    )
    warnings = list(report.get("warnings", []))
    errors = list(report.get("errors", []))
    sample_marker_ok = False
    if df is not None and not df.empty and "source" in df.columns and "data_mode" in df.columns:
        source_values = df["source"].fillna("").astype(str).str.upper()
        mode_values = df["data_mode"].fillna("").astype(str).str.upper()
        sample_marker_ok = bool(source_values.eq("SAMPLE").all() and mode_values.eq("SAMPLE").all())
        if not sample_marker_ok:
            errors.append("SAMPLE 快照必须在 source 和 data_mode 中标记为 SAMPLE。")
    elif df is not None and not df.empty:
        errors.append("SAMPLE 快照缺少 source 或 data_mode 标记列。")

    error_count = len(errors)
    warning_count = len(warnings)
    if error_count:
        label = "SAMPLE 数据契约不通过"
    elif warning_count:
        label = "SAMPLE 数据契约通过但有警告"
    else:
        label = "SAMPLE 数据契约通过"
    report.update(
        {
            "contract_name": "sample_snapshot",
            "contract_ok": error_count == 0,
            "contract_label": label,
            "sample_marker_ok": sample_marker_ok,
            "warning_count": warning_count,
            "error_count": error_count,
            "warnings": warnings,
            "errors": errors,
        }
    )
    return report


def validate_snapshot_csv_file(path: str | Path, sample: bool = False) -> dict:
    csv_path = Path(path)
    if not csv_path.exists():
        return {
            "file_path": str(csv_path),
            "file_name": csv_path.name,
            "contract_ok": False,
            "contract_label": "CSV 文件不存在",
            "row_count": 0,
            "warning_count": 0,
            "error_count": 1,
            "warnings": [],
            "errors": ["CSV 文件不存在。"],
        }
    try:
        df = pd.read_csv(csv_path, dtype={"sector_code": str})
    except Exception as exc:
        return {
            "file_path": str(csv_path),
            "file_name": csv_path.name,
            "contract_ok": False,
            "contract_label": "CSV 文件不可读",
            "row_count": 0,
            "warning_count": 0,
            "error_count": 1,
            "warnings": [],
            "errors": [f"CSV 文件不可读：{exc}"],
        }
    report = validate_sample_snapshot_dataframe(df, csv_path.name) if sample else validate_snapshot_dataframe(df, csv_path.name)
    report["file_path"] = str(csv_path)
    report["file_name"] = csv_path.name
    return report


def validate_snapshot_directory(directory: str | Path, sample: bool = False) -> dict:
    root = Path(directory)
    warnings: list[str] = []
    errors: list[str] = []
    if not root.exists():
        return {
            "directory": str(root),
            "sample": sample,
            "file_count": 0,
            "valid_file_count": 0,
            "invalid_file_count": 0,
            "row_count": 0,
            "contract_label": "目录不存在",
            "contract_ok": False,
            "warning_count": 1,
            "error_count": 0,
            "warnings": ["快照目录不存在。"],
            "errors": [],
            "file_reports": [],
        }
    files = sorted(root.glob("sector_flow_*.csv"))
    if not files:
        warnings.append("快照目录中没有 sector_flow_*.csv 文件。")
    file_reports = [validate_snapshot_csv_file(path, sample=sample) for path in files]
    valid_count = sum(1 for item in file_reports if item.get("contract_ok"))
    invalid_reports = [item for item in file_reports if not item.get("contract_ok")]
    for item in invalid_reports:
        errors.extend(f"{item.get('file_name')}: {error}" for error in item.get("errors", []))
        warnings.extend(f"{item.get('file_name')}: {warning}" for warning in item.get("warnings", []))
    row_count = sum(int(item.get("row_count", 0) or 0) for item in file_reports)
    error_count = len(errors)
    warning_count = len(warnings)
    if error_count:
        label = "目录数据契约不通过"
    elif warning_count:
        label = "目录数据契约通过但有警告"
    else:
        label = "目录数据契约通过"
    return {
        "directory": str(root),
        "sample": sample,
        "file_count": len(files),
        "valid_file_count": valid_count,
        "invalid_file_count": len(invalid_reports),
        "row_count": row_count,
        "contract_label": label,
        "contract_ok": error_count == 0,
        "warning_count": warning_count,
        "error_count": error_count,
        "warnings": warnings,
        "errors": errors,
        "file_reports": file_reports,
    }


def summarize_data_contract_report(report: dict) -> str:
    label = report.get("contract_label", "数据契约未检查")
    file_count = report.get("file_count")
    row_count = report.get("row_count", 0)
    if file_count is not None:
        return f"{label}：共检查 {file_count} 个快照文件、{row_count} 行。CSV 仍是主数据来源，SAMPLE 仅用于公开演示。"
    return f"{label}：共检查 {row_count} 行。该检查只验证结构和标记，不生成投资判断。"


def validate_data_contract_text(text: str) -> list[str]:
    return sorted({word for word in FORBIDDEN_CONTRACT_WORDS if word in str(text)})
