from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.config import TIMEZONE
from src.snapshot_catalog import (
    DEFAULT_COLLECTOR_AUDIT_LOG_PATH,
    build_snapshot_catalog,
)


SUCCESS_STATUSES = {"success"}
DUPLICATE_STATUSES = {"duplicate_skipped"}
DRY_RUN_STATUSES = {"dry_run"}
NO_NETWORK_STATUSES = {"no_network"}
FAILURE_STATUSES = {"fetch_error", "empty_fetch", "contract_error", "write_error"}
NON_WRITE_INTENT_STATUSES = DRY_RUN_STATUSES | NO_NETWORK_STATUSES


def _parse_timestamp(value: object) -> pd.Timestamp | None:
    if value is None or pd.isna(value):
        return None
    try:
        parsed = pd.Timestamp(str(value))
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize(TIMEZONE)
    return parsed.tz_convert(TIMEZONE)


def _now(now: datetime | pd.Timestamp | None = None) -> pd.Timestamp:
    if now is None:
        return pd.Timestamp.now(tz=TIMEZONE)
    parsed = pd.Timestamp(now)
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize(TIMEZONE)
    return parsed.tz_convert(TIMEZONE)


def load_collector_audit_log(log_path: str | Path = DEFAULT_COLLECTOR_AUDIT_LOG_PATH) -> dict:
    path = Path(log_path)
    records: list[dict] = []
    malformed_line_count = 0
    warnings: list[str] = []
    if not path.exists():
        return {
            "log_exists": False,
            "log_path": str(path),
            "records": [],
            "runs_df": pd.DataFrame(),
            "valid_log_records": 0,
            "malformed_line_count": 0,
            "warnings": ["collector audit log 尚未创建。"],
            "errors": [],
        }
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return {
            "log_exists": True,
            "log_path": str(path),
            "records": [],
            "runs_df": pd.DataFrame(),
            "valid_log_records": 0,
            "malformed_line_count": 0,
            "warnings": [],
            "errors": [f"collector audit log 不可读：{exc}"],
        }
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                records.append(parsed)
            else:
                malformed_line_count += 1
        except Exception:
            malformed_line_count += 1
    if malformed_line_count:
        warnings.append(f"collector audit log 存在 {malformed_line_count} 行无法解析。")
    df = pd.DataFrame(records)
    if not df.empty and "timestamp" in df.columns:
        df["_parsed_timestamp"] = df["timestamp"].map(_parse_timestamp)
        df = df.sort_values("_parsed_timestamp", ascending=False, na_position="last").reset_index(drop=True)
    return {
        "log_exists": True,
        "log_path": str(path),
        "records": records,
        "runs_df": df,
        "valid_log_records": int(len(records)),
        "malformed_line_count": malformed_line_count,
        "warnings": warnings,
        "errors": [],
    }


def _status_counts(df: pd.DataFrame) -> dict:
    if df.empty or "status" not in df.columns:
        return {}
    return df["status"].fillna("unknown").astype(str).value_counts().to_dict()


def _category_counts(df: pd.DataFrame) -> dict:
    if df.empty or "error_category" not in df.columns:
        return {}
    values = df["error_category"].dropna().astype(str)
    values = values[values.ne("")]
    return values.value_counts().to_dict()


def _latest_timestamp(df: pd.DataFrame, statuses: set[str] | None = None) -> str | None:
    if df.empty or "_parsed_timestamp" not in df.columns:
        return None
    work = df
    if statuses is not None and "status" in work.columns:
        work = work[work["status"].astype(str).isin(statuses)]
    work = work.dropna(subset=["_parsed_timestamp"])
    if work.empty:
        return None
    return work.iloc[0]["_parsed_timestamp"].isoformat()


def _count_today(df: pd.DataFrame, now: pd.Timestamp, statuses: set[str] | None = None) -> int:
    if df.empty or "_parsed_timestamp" not in df.columns:
        return 0
    work = df.dropna(subset=["_parsed_timestamp"]).copy()
    if statuses is not None and "status" in work.columns:
        work = work[work["status"].astype(str).isin(statuses)]
    if work.empty:
        return 0
    today = now.normalize()
    return int(work["_parsed_timestamp"].map(lambda value: value.tz_convert(TIMEZONE).normalize() == today).sum())


def _consecutive_failure_count(df: pd.DataFrame) -> int:
    if df.empty or "status" not in df.columns:
        return 0
    count = 0
    for status in df["status"].fillna("unknown").astype(str).tolist():
        if status in FAILURE_STATUSES:
            count += 1
            continue
        break
    return count


def build_ingestion_metrics(
    log_path: str | Path = DEFAULT_COLLECTOR_AUDIT_LOG_PATH,
    now: datetime | pd.Timestamp | None = None,
    recent_n: int = 10,
) -> dict:
    report = load_collector_audit_log(log_path)
    df = report.get("runs_df", pd.DataFrame())
    current = _now(now)
    status_counts = _status_counts(df)
    success_count = sum(int(status_counts.get(status, 0)) for status in SUCCESS_STATUSES)
    duplicate_count = sum(int(status_counts.get(status, 0)) for status in DUPLICATE_STATUSES)
    dry_run_count = sum(int(status_counts.get(status, 0)) for status in DRY_RUN_STATUSES)
    no_network_count = sum(int(status_counts.get(status, 0)) for status in NO_NETWORK_STATUSES)
    failure_count = sum(int(status_counts.get(status, 0)) for status in FAILURE_STATUSES)
    total_runs = int(len(df)) if isinstance(df, pd.DataFrame) else 0
    write_intent_run_count = max(0, total_runs - dry_run_count - no_network_count)
    success_rate = round(success_count / write_intent_run_count, 4) if write_intent_run_count else None
    recent_n = max(1, min(int(recent_n or 10), 100))
    recent = df.head(recent_n) if isinstance(df, pd.DataFrame) else pd.DataFrame()
    recent_counts = _status_counts(recent)
    recent_write_intent = max(
        0,
        int(len(recent))
        - sum(int(recent_counts.get(status, 0)) for status in NON_WRITE_INTENT_STATUSES),
    )
    recent_success = sum(int(recent_counts.get(status, 0)) for status in SUCCESS_STATUSES)
    recent_success_rate = round(recent_success / recent_write_intent, 4) if recent_write_intent else None
    provider_counts = {}
    api_counts = {}
    distinct_collection_dates = 0
    if isinstance(df, pd.DataFrame) and not df.empty:
        if "provider" in df.columns:
            provider_counts = df["provider"].dropna().astype(str).value_counts().to_dict()
        if "api_name" in df.columns:
            api_counts = df["api_name"].dropna().astype(str).value_counts().to_dict()
        if "trade_date" in df.columns:
            distinct_collection_dates = int(df["trade_date"].dropna().astype(str).nunique())
    if total_runs == 0:
        label = "暂无 ingestion 记录"
        reason = "collector audit log 暂无可解析运行记录；公开 demo 和 CI 不要求真实采集日志存在。"
    elif write_intent_run_count == 0:
        label = "仅有非写入检查记录"
        reason = "当前日志仅包含 dry-run 或 no-network 检查，不代表真实缓存写入成功率。"
    elif failure_count and not success_count:
        label = "近期真实采集需排查"
        reason = "已有写入意图记录，但尚未看到成功写入状态。"
    else:
        label = "ingestion 指标可用"
        reason = "collector audit log 可用于观察本地真实缓存采集尝试与结果分布。"
    return {
        "metrics_label": label,
        "metrics_reason": reason,
        "log_exists": bool(report.get("log_exists")),
        "log_path": report.get("log_path"),
        "total_runs": total_runs,
        "valid_log_records": int(report.get("valid_log_records", 0) or 0),
        "malformed_line_count": int(report.get("malformed_line_count", 0) or 0),
        "success_count": success_count,
        "failure_count": failure_count,
        "duplicate_skipped_count": duplicate_count,
        "dry_run_count": dry_run_count,
        "no_network_count": no_network_count,
        "write_intent_run_count": write_intent_run_count,
        "success_rate": success_rate,
        "success_rate_denominator_semantics": "success / write-intent runs; dry_run and no_network excluded",
        "status_counts": status_counts,
        "error_category_counts": _category_counts(df),
        "runs_today": _count_today(df, current),
        "successes_today": _count_today(df, current, SUCCESS_STATUSES),
        "failures_today": _count_today(df, current, FAILURE_STATUSES),
        "latest_run_at": _latest_timestamp(df),
        "latest_success_at": _latest_timestamp(df, SUCCESS_STATUSES),
        "consecutive_failure_count": _consecutive_failure_count(df),
        "recent_success_rate": recent_success_rate,
        "distinct_collection_dates": distinct_collection_dates,
        "provider_counts": provider_counts,
        "api_counts": api_counts,
        "warning_count": len(report.get("warnings", [])),
        "error_count": len(report.get("errors", [])),
        "warnings": report.get("warnings", []),
        "errors": report.get("errors", []),
    }


def assess_real_cache_coverage(
    data_dir: str | Path = "data/ticks",
    now: datetime | pd.Timestamp | None = None,
    min_intraday_points: int = 3,
) -> dict:
    current = _now(now)
    threshold = max(1, int(min_intraday_points or 3))
    catalog = build_snapshot_catalog(str(data_dir))
    if catalog.empty:
        return {
            "real_snapshot_count": 0,
            "real_date_count": 0,
            "snapshots_today": 0,
            "distinct_captured_times_today": 0,
            "latest_real_snapshot_time": None,
            "latest_real_trade_date": None,
            "cache_freshness_status": "missing",
            "enough_intraday_points": False,
            "coverage_label": "no_real_data",
            "coverage_reason": "本地 data/ticks 暂无真实 CSV 快照。",
            "coverage_threshold": threshold,
            "warnings": ["未发现本地真实缓存 CSV。"],
            "errors": [],
        }
    readable = catalog[catalog["is_readable"].fillna(False)].copy()
    if readable.empty:
        return {
            "real_snapshot_count": int(len(catalog)),
            "real_date_count": 0,
            "snapshots_today": 0,
            "distinct_captured_times_today": 0,
            "latest_real_snapshot_time": None,
            "latest_real_trade_date": None,
            "cache_freshness_status": "unreadable",
            "enough_intraday_points": False,
            "coverage_label": "no_real_data",
            "coverage_reason": "发现真实缓存文件，但当前均不可读。",
            "coverage_threshold": threshold,
            "warnings": ["真实缓存 CSV 不可读或结构异常。"],
            "errors": [],
        }
    today_str = current.strftime("%Y-%m-%d")
    today_rows = readable[readable["snapshot_date"].astype(str).eq(today_str)]
    snapshots_today = int(len(today_rows))
    distinct_today = int(today_rows["captured_time_count"].fillna(0).max()) if not today_rows.empty else 0
    latest = readable.iloc[0]
    total_dates = int(readable["snapshot_date"].nunique())
    total_files = int(len(readable))
    latest_trade_date = str(latest.get("snapshot_date") or "")
    if latest_trade_date == today_str:
        freshness = "today"
    else:
        freshness = "historical"
    enough = distinct_today >= threshold
    if total_files <= 0:
        label = "no_real_data"
        reason = "本地 data/ticks 暂无真实 CSV 快照。"
    elif total_files == 1 and int(latest.get("captured_time_count", 0) or 0) <= 1:
        label = "single_snapshot"
        reason = "当前真实缓存只有单个快照点，适合确认采集链路，不足以代表完整日内覆盖。"
    elif enough:
        label = "usable_intraday_coverage"
        reason = f"今日真实缓存 captured_time 数量达到 {distinct_today}，满足本地观察阈值 {threshold}。"
    else:
        label = "limited_intraday_coverage"
        reason = f"真实缓存已存在，但今日 captured_time 数量为 {distinct_today}，低于本地观察阈值 {threshold}。"
    return {
        "real_snapshot_count": total_files,
        "real_date_count": total_dates,
        "snapshots_today": snapshots_today,
        "distinct_captured_times_today": distinct_today,
        "latest_real_snapshot_time": latest.get("latest_captured_time"),
        "latest_real_trade_date": latest_trade_date or None,
        "cache_freshness_status": freshness,
        "enough_intraday_points": enough,
        "coverage_label": label,
        "coverage_reason": reason,
        "coverage_threshold": threshold,
        "warnings": [],
        "errors": [],
    }


def build_collection_operations_status(
    policy_decision: dict,
    metrics: dict,
    coverage: dict,
    collector_summary: dict | None = None,
) -> dict:
    warnings = []
    errors = []
    warnings.extend(metrics.get("warnings", []))
    warnings.extend(coverage.get("warnings", []))
    errors.extend(metrics.get("errors", []))
    errors.extend(coverage.get("errors", []))
    if not policy_decision.get("eligible"):
        label = "采集暂不启动"
        reason = policy_decision.get("policy_reason", "当前策略不允许启动采集。")
    elif metrics.get("consecutive_failure_count", 0) >= 3:
        label = "采集链路需排查"
        reason = "collector audit log 显示连续失败次数较多，建议先查看 provider diagnostic。"
    elif coverage.get("coverage_label") == "usable_intraday_coverage":
        label = "真实缓存覆盖可用"
        reason = "本地真实缓存已达到当前观察阈值，可用于只读观察。"
    else:
        label = "可按需启动采集"
        reason = "采集策略允许启动，但真实缓存覆盖仍有限。"
    return {
        "operations_label": label,
        "operations_reason": reason,
        "policy_status": policy_decision.get("policy_status"),
        "metrics_label": metrics.get("metrics_label"),
        "coverage_label": coverage.get("coverage_label"),
        "latest_success_at": metrics.get("latest_success_at"),
        "success_rate": metrics.get("success_rate"),
        "consecutive_failure_count": metrics.get("consecutive_failure_count"),
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
        "collector_summary": collector_summary or {},
    }


def summarize_ingestion_metrics(metrics: dict) -> str:
    return (
        f"当前 ingestion 日志状态：{metrics.get('metrics_label', '--')}。"
        f" 写入意图运行 {metrics.get('write_intent_run_count', 0)} 次，"
        f"成功 {metrics.get('success_count', 0)} 次；成功率分母口径为 "
        f"{metrics.get('success_rate_denominator_semantics', 'success / write-intent runs')}。"
        " 该摘要只描述本地采集运行记录，不代表真实行情完整性。"
    )


def validate_ingestion_metrics_text(text: str) -> list[str]:
    forbidden = [
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
    ]
    return sorted({word for word in forbidden if word in str(text or "")})
