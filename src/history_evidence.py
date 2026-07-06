from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.data_contracts import validate_real_snapshot_dataframe, validate_sample_snapshot_dataframe
from src.providers.akshare_sector_flow import build_schema_fingerprint
from src.snapshot_catalog import SNAPSHOT_PATTERN, parse_snapshot_date


UNKNOWN = "unknown"

FORBIDDEN_HISTORY_EVIDENCE_WORDS = (
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


def _safe_relpath(path: Path, root: Path | None = None) -> str:
    root = root or Path.cwd()
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _safe_first_value(df: pd.DataFrame, column: str) -> str:
    if column not in df.columns or df.empty:
        return UNKNOWN
    values = df[column].dropna().astype(str).str.strip()
    values = values[values.ne("")]
    if values.empty:
        return UNKNOWN
    return str(values.iloc[0])


def _safe_latest_time(values: Iterable[object]) -> str | None:
    clean = sorted({str(value) for value in values if pd.notna(value) and str(value).strip()})
    return clean[-1] if clean else None


def normalize_captured_time_bucket(captured_time: object, bucket_minutes: int = 1) -> str | None:
    if captured_time is None or pd.isna(captured_time):
        return None
    bucket_minutes = max(1, int(bucket_minutes or 1))
    parsed = pd.to_datetime(str(captured_time), errors="coerce")
    if pd.isna(parsed):
        return str(captured_time).strip()[:5] or None
    minute = int(parsed.minute)
    bucketed_minute = (minute // bucket_minutes) * bucket_minutes
    bucketed = parsed.replace(minute=bucketed_minute, second=0, microsecond=0)
    return bucketed.strftime("%H:%M")


def compute_file_sha256(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _make_snapshot_id(source_mode: str, rel_path: str, trade_date: str | None, captured_time: str | None, file_sha256: str) -> str:
    payload = json.dumps(
        {
            "source_mode": str(source_mode or UNKNOWN).upper(),
            "relative_path": rel_path,
            "trade_date": trade_date or UNKNOWN,
            "captured_time": captured_time or UNKNOWN,
            "file_sha256": file_sha256,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def inspect_snapshot_evidence(
    path: str | Path,
    cache_root: str | Path | None = None,
    source_mode: str = "REAL",
    bucket_minutes: int = 1,
) -> dict:
    file_path = Path(path)
    root = Path(cache_root) if cache_root is not None else file_path.parent
    rel_path = _safe_relpath(file_path, root)
    source_mode = str(source_mode or "REAL").upper()
    warnings: list[str] = []
    errors: list[str] = []
    trade_date = parse_snapshot_date(file_path) or UNKNOWN
    file_sha = UNKNOWN
    modified_at = None
    try:
        stat = file_path.stat()
        modified_at = pd.Timestamp.fromtimestamp(stat.st_mtime).isoformat()
        file_sha = compute_file_sha256(file_path)
    except Exception as exc:
        errors.append(f"文件不可读：{type(exc).__name__}")

    base = {
        "snapshot_id": _make_snapshot_id(source_mode, rel_path, trade_date, None, file_sha),
        "file_name": file_path.name,
        "relative_path": rel_path,
        "cache_relative_path": rel_path,
        "trade_date": trade_date,
        "captured_time": None,
        "captured_time_bucket": None,
        "captured_times": [],
        "captured_time_buckets": [],
        "captured_time_count": 0,
        "captured_at": None,
        "provider": UNKNOWN,
        "api_name": UNKNOWN,
        "source": UNKNOWN,
        "data_mode": UNKNOWN,
        "row_count": 0,
        "schema_fingerprint": UNKNOWN,
        "contract_status": "not_checked",
        "contract_ok": False,
        "file_sha256": file_sha,
        "modified_at": modified_at,
        "is_readable": False,
        "is_empty": True,
        "is_malformed": True,
        "source_mode": source_mode,
        "warnings": warnings,
        "errors": errors,
    }
    if errors:
        base["snapshot_id"] = _make_snapshot_id(source_mode, rel_path, trade_date, None, file_sha)
        return base
    try:
        df = pd.read_csv(file_path)
    except Exception as exc:
        errors.append(f"CSV 解析失败：{type(exc).__name__}")
        return base

    base["is_readable"] = True
    base["row_count"] = int(len(df))
    base["is_empty"] = bool(df.empty)
    base["schema_fingerprint"] = build_schema_fingerprint(df.columns) if len(df.columns) else UNKNOWN
    if df.empty:
        errors.append("CSV 为空。")
        base["contract_status"] = "empty"
        return base

    if "trade_date" in df.columns:
        candidate_date = _safe_first_value(df, "trade_date")
        if candidate_date != UNKNOWN:
            base["trade_date"] = candidate_date

    captured_times = []
    if "captured_time" in df.columns:
        captured_times = sorted({str(value) for value in df["captured_time"].dropna().astype(str) if str(value).strip()})
    latest_captured_time = _safe_latest_time(captured_times)
    captured_buckets = sorted(
        {
            bucket
            for bucket in (normalize_captured_time_bucket(value, bucket_minutes=bucket_minutes) for value in captured_times)
            if bucket
        }
    )
    base["captured_time"] = latest_captured_time
    base["captured_time_bucket"] = normalize_captured_time_bucket(latest_captured_time, bucket_minutes=bucket_minutes)
    base["captured_times"] = captured_times
    base["captured_time_buckets"] = captured_buckets
    base["captured_time_count"] = int(len(captured_times))
    if "captured_at" in df.columns:
        captured_at = pd.to_datetime(df["captured_at"], errors="coerce").dropna()
        if not captured_at.empty:
            base["captured_at"] = captured_at.max().isoformat()
    base["provider"] = _safe_first_value(df, "provider")
    base["api_name"] = _safe_first_value(df, "api_name")
    base["source"] = _safe_first_value(df, "source")
    base["data_mode"] = _safe_first_value(df, "data_mode")
    if source_mode == "SAMPLE":
        contract = validate_sample_snapshot_dataframe(df, context=rel_path)
    else:
        contract = validate_real_snapshot_dataframe(df, context=rel_path)
    base["contract_status"] = str(contract.get("contract_label") or UNKNOWN)
    base["contract_ok"] = bool(contract.get("contract_ok"))
    warnings.extend(str(item) for item in contract.get("warnings", []))
    errors.extend(str(item) for item in contract.get("errors", []))
    base["is_malformed"] = bool(errors)
    base["snapshot_id"] = _make_snapshot_id(
        source_mode,
        rel_path,
        str(base.get("trade_date") or UNKNOWN),
        latest_captured_time,
        file_sha,
    )
    return base


def build_snapshot_manifest(
    data_dir: str | Path = "data/ticks",
    source_mode: str = "REAL",
    bucket_minutes: int = 1,
) -> pd.DataFrame:
    directory = Path(data_dir)
    if not directory.exists():
        return pd.DataFrame()
    records = []
    for path in sorted(directory.glob("sector_flow_*.csv")):
        if not SNAPSHOT_PATTERN.match(path.name):
            continue
        records.append(
            inspect_snapshot_evidence(
                path,
                cache_root=directory,
                source_mode=source_mode,
                bucket_minutes=bucket_minutes,
            )
        )
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    return df.sort_values(["trade_date", "captured_time", "file_name"], na_position="last").reset_index(drop=True)


def _valid_manifest(manifest_df: pd.DataFrame | None) -> pd.DataFrame:
    if manifest_df is None or manifest_df.empty:
        return pd.DataFrame()
    df = manifest_df.copy()
    if "is_readable" in df.columns:
        df = df[df["is_readable"].fillna(False)]
    if "is_empty" in df.columns:
        df = df[~df["is_empty"].fillna(True)]
    return df


def build_historical_coverage_summary(manifest_df: pd.DataFrame | None) -> dict:
    total = 0 if manifest_df is None else int(len(manifest_df))
    if manifest_df is None or manifest_df.empty:
        return {
            "total_snapshot_count": 0,
            "valid_snapshot_count": 0,
            "malformed_snapshot_count": 0,
            "empty_snapshot_count": 0,
            "trade_date_count": 0,
            "available_trade_dates": [],
            "earliest_trade_date": None,
            "latest_trade_date": None,
            "latest_captured_time": None,
            "provider_counts": {},
            "api_counts": {},
            "schema_fingerprint_counts": {},
            "schema_fingerprint_count": 0,
            "schema_consistent": False,
            "contract_pass_count": 0,
            "contract_fail_count": 0,
            "unknown_metadata_count": 0,
            "snapshots_by_date": {},
            "captured_times_by_date": {},
            "captured_bucket_count_by_date": {},
            "coverage_label": "暂无历史证据",
            "coverage_reason": "当前目录没有可识别的 CSV 快照。CSV 仍是主数据来源。",
        }
    df = manifest_df.copy()
    valid = _valid_manifest(df)
    dates = sorted(valid.get("trade_date", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
    provider_counts = df.get("provider", pd.Series(dtype=str)).fillna(UNKNOWN).astype(str).value_counts().to_dict()
    api_counts = df.get("api_name", pd.Series(dtype=str)).fillna(UNKNOWN).astype(str).value_counts().to_dict()
    schema_counts = df.get("schema_fingerprint", pd.Series(dtype=str)).fillna(UNKNOWN).astype(str).value_counts().to_dict()
    unknown_metadata_count = 0
    for column in ("provider", "api_name", "source", "data_mode", "schema_fingerprint"):
        if column in df.columns:
            values = df[column].fillna(UNKNOWN).astype(str).str.lower()
            unknown_metadata_count += int(values.isin({UNKNOWN, "", "none", "nan"}).sum())
    captured_times_by_date: dict[str, list[str]] = {}
    captured_bucket_count_by_date: dict[str, int] = {}
    for trade_date, group in valid.groupby("trade_date", dropna=True):
        times: set[str] = set()
        buckets: set[str] = set()
        for _, row in group.iterrows():
            times.update([str(item) for item in row.get("captured_times", []) if item])
            buckets.update([str(item) for item in row.get("captured_time_buckets", []) if item])
            if row.get("captured_time"):
                times.add(str(row.get("captured_time")))
            if row.get("captured_time_bucket"):
                buckets.add(str(row.get("captured_time_bucket")))
        captured_times_by_date[str(trade_date)] = sorted(times)
        captured_bucket_count_by_date[str(trade_date)] = len(buckets)
    latest_time = None
    if captured_times_by_date:
        all_times = [item for values in captured_times_by_date.values() for item in values]
        latest_time = sorted(all_times)[-1] if all_times else None
    schema_fingerprint_count = len([key for key in schema_counts if key and str(key).lower() != UNKNOWN])
    contract_pass = int(df.get("contract_ok", pd.Series(dtype=bool)).fillna(False).sum()) if "contract_ok" in df.columns else 0
    summary = {
        "total_snapshot_count": total,
        "valid_snapshot_count": int(len(valid)),
        "malformed_snapshot_count": int(df.get("is_malformed", pd.Series(dtype=bool)).fillna(False).sum()),
        "empty_snapshot_count": int(df.get("is_empty", pd.Series(dtype=bool)).fillna(False).sum()),
        "trade_date_count": int(len(dates)),
        "available_trade_dates": dates,
        "earliest_trade_date": dates[0] if dates else None,
        "latest_trade_date": dates[-1] if dates else None,
        "latest_captured_time": latest_time,
        "provider_counts": provider_counts,
        "api_counts": api_counts,
        "schema_fingerprint_counts": schema_counts,
        "schema_fingerprint_count": schema_fingerprint_count,
        "schema_consistent": bool(schema_fingerprint_count == 1),
        "contract_pass_count": contract_pass,
        "contract_fail_count": total - contract_pass,
        "unknown_metadata_count": unknown_metadata_count,
        "snapshots_by_date": valid["trade_date"].astype(str).value_counts().sort_index().to_dict() if not valid.empty else {},
        "captured_times_by_date": captured_times_by_date,
        "captured_bucket_count_by_date": captured_bucket_count_by_date,
    }
    if not valid.empty:
        summary["coverage_label"] = "历史证据可用"
        summary["coverage_reason"] = "已从本地 CSV 快照恢复历史覆盖、来源字段、契约状态和 schema fingerprint。"
    else:
        summary["coverage_label"] = "暂无有效历史证据"
        summary["coverage_reason"] = "已发现 CSV 文件，但尚无可读且非空的有效快照。"
    return summary


def build_coverage_matrix(manifest_df: pd.DataFrame | None, bucket_minutes: int = 1) -> pd.DataFrame:
    valid = _valid_manifest(manifest_df)
    if valid.empty:
        return pd.DataFrame()
    rows = []
    for _, row in valid.iterrows():
        trade_date = row.get("trade_date")
        if not trade_date:
            continue
        buckets = row.get("captured_time_buckets") or []
        if not buckets and row.get("captured_time"):
            bucket = normalize_captured_time_bucket(row.get("captured_time"), bucket_minutes=bucket_minutes)
            buckets = [bucket] if bucket else []
        for bucket in sorted(set(str(item) for item in buckets if item)):
            rows.append({"trade_date": str(trade_date), "captured_time_bucket": bucket, "snapshot_count": 1})
    if not rows:
        return pd.DataFrame()
    long_df = pd.DataFrame(rows)
    matrix = (
        long_df.pivot_table(
            index="trade_date",
            columns="captured_time_bucket",
            values="snapshot_count",
            aggfunc="sum",
            fill_value=0,
        )
        .sort_index()
        .reset_index()
    )
    matrix.columns = [str(column) for column in matrix.columns]
    return matrix


def classify_historical_evidence_readiness(
    summary: dict,
    min_multi_day_dates: int = 3,
    min_intraday_buckets: int = 3,
    min_snapshots_per_ready_date: int = 1,
) -> dict:
    valid_count = int(summary.get("valid_snapshot_count", 0) or 0)
    date_count = int(summary.get("trade_date_count", 0) or 0)
    bucket_counts = {
        str(key): int(value or 0)
        for key, value in (summary.get("captured_bucket_count_by_date") or {}).items()
    }
    max_buckets = max(bucket_counts.values()) if bucket_counts else 0
    snapshots_by_date = {
        str(key): int(value or 0)
        for key, value in (summary.get("snapshots_by_date") or {}).items()
    }
    ready_dates = sum(1 for value in snapshots_by_date.values() if value >= min_snapshots_per_ready_date)
    if valid_count == 0 or date_count == 0:
        state = "no_real_history"
        label = "暂无真实历史证据"
        reason = "当前没有可读的本地真实 CSV 历史快照。"
    elif valid_count == 1 and max_buckets <= 1:
        state = "single_snapshot"
        label = "单快照证据"
        reason = "当前只有一个有效历史快照，适合回放单次状态，不适合作跨日期观察。"
    elif date_count == 1 and max_buckets >= min_intraday_buckets:
        state = "single_day_intraday"
        label = "单日多时间点证据"
        reason = "当前有一个交易日内的多个时间点，可用于日内回放证据说明。"
    elif date_count >= min_multi_day_dates and ready_dates >= min_multi_day_dates:
        state = "multi_day_ready"
        label = "多日历史证据可用"
        reason = "当前已覆盖多个交易日，可作为多日主题观察的来源证据。"
    else:
        state = "limited_multi_day"
        label = "有限多日历史证据"
        reason = "当前已有多个日期，但样本仍较少，适合轻量历史观察。"
    return {
        "readiness_state": state,
        "readiness_label": label,
        "readiness_reason": reason,
        "valid_snapshot_count": valid_count,
        "trade_date_count": date_count,
        "max_intraday_bucket_count": max_buckets,
        "min_multi_day_dates": int(min_multi_day_dates),
        "min_intraday_buckets": int(min_intraday_buckets),
        "min_snapshots_per_ready_date": int(min_snapshots_per_ready_date),
    }


def resolve_replay_evidence(
    selected_trade_date: str | None,
    manifest_df: pd.DataFrame | None,
    source_mode: str = "REAL",
    mode: str = "HISTORY",
) -> dict:
    if manifest_df is None or manifest_df.empty or not selected_trade_date:
        return {
            "mode": mode,
            "source_mode": source_mode,
            "selected_trade_date": selected_trade_date,
            "evidence_state": "no_evidence",
            "snapshot_count": 0,
            "snapshot_ids": [],
            "captured_time_start": None,
            "captured_time_end": None,
            "captured_time_count": 0,
            "provider_counts": {},
            "api_counts": {},
            "schema_fingerprints": [],
            "schema_consistent": False,
            "contract_pass_count": 0,
            "warnings": ["未找到该日期的历史回放证据。"],
        }
    df = _valid_manifest(manifest_df)
    if df.empty or "trade_date" not in df.columns:
        return resolve_replay_evidence(selected_trade_date, None, source_mode=source_mode, mode=mode)
    selected = df[df["trade_date"].astype(str).eq(str(selected_trade_date))]
    if selected.empty:
        return {
            **resolve_replay_evidence(selected_trade_date, None, source_mode=source_mode, mode=mode),
            "warnings": [f"未找到日期 {selected_trade_date} 的历史回放证据。"],
        }
    times: set[str] = set()
    for _, row in selected.iterrows():
        times.update(str(item) for item in row.get("captured_times", []) if item)
        if row.get("captured_time"):
            times.add(str(row.get("captured_time")))
    sorted_times = sorted(times)
    schema_values = sorted(
        {
            str(value)
            for value in selected.get("schema_fingerprint", pd.Series(dtype=str)).dropna().astype(str)
            if str(value).lower() != UNKNOWN
        }
    )
    return {
        "mode": mode,
        "source_mode": source_mode,
        "selected_trade_date": selected_trade_date,
        "evidence_state": "available",
        "snapshot_count": int(len(selected)),
        "snapshot_ids": selected.get("snapshot_id", pd.Series(dtype=str)).dropna().astype(str).tolist(),
        "captured_time_start": sorted_times[0] if sorted_times else None,
        "captured_time_end": sorted_times[-1] if sorted_times else None,
        "captured_time_count": int(len(sorted_times)),
        "provider_counts": selected.get("provider", pd.Series(dtype=str)).fillna(UNKNOWN).astype(str).value_counts().to_dict(),
        "api_counts": selected.get("api_name", pd.Series(dtype=str)).fillna(UNKNOWN).astype(str).value_counts().to_dict(),
        "schema_fingerprints": schema_values,
        "schema_consistent": len(schema_values) <= 1,
        "contract_pass_count": int(selected.get("contract_ok", pd.Series(dtype=bool)).fillna(False).sum()),
        "warnings": [],
    }


def validate_history_evidence_text(text: str) -> list[str]:
    value = str(text or "")
    return [word for word in FORBIDDEN_HISTORY_EVIDENCE_WORDS if word in value]
