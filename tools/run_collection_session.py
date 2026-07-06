from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.collection_policy import decide_collection_eligibility, get_default_collection_policy  # noqa: E402
from src.config import DEFAULT_SECTOR_TYPE, TIMEZONE  # noqa: E402
from src.ingestion_metrics import build_ingestion_metrics  # noqa: E402
from tools.collect_market_snapshot import DEFAULT_AUDIT_LOG_PATH, run_collector  # noqa: E402


SUCCESS_LIKE_STATUSES = {"success", "dry_run"}
FAILURE_STATUSES = {"fetch_error", "empty_fetch", "contract_error", "write_error"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="有限次数运行本地真实行情 one-shot collector。不会常驻运行，也不会自动创建调度器。",
    )
    parser.add_argument("--max-runs", type=int, default=1, help="本次 session 最多尝试次数，默认 1，最大 100。")
    parser.add_argument("--interval-seconds", type=float, default=60.0, help="两次尝试之间的等待秒数，默认 60。")
    policy = parser.add_mutually_exclusive_group()
    policy.add_argument("--respect-session", dest="respect_session", action="store_true", help="遵守本地采集观察窗口。")
    policy.add_argument("--ignore-session", dest="respect_session", action="store_false", help="忽略采集观察窗口，仅用于手动诊断。")
    parser.set_defaults(respect_session=True)
    parser.add_argument("--dry-run", action="store_true", help="传递给 collector：抓取并检查，但不写 CSV。")
    parser.add_argument("--no-network", action="store_true", help="传递给 collector：不访问 AKShare，不写 CSV。")
    parser.add_argument("--no-log", action="store_true", help="传递给 collector：不写 collector audit log。")
    parser.add_argument("--stop-on-success", action="store_true", help="出现 success 或 dry_run 状态后停止后续尝试。")
    parser.add_argument("--stop-on-contract-error", action="store_true", help="出现 contract_error 后停止后续尝试。")
    parser.add_argument("--output-dir", default="data/ticks", help="真实缓存输出目录，默认 data/ticks。")
    parser.add_argument("--log-path", default=DEFAULT_AUDIT_LOG_PATH, help="collector audit JSONL 路径。")
    parser.add_argument("--sector-type", default=DEFAULT_SECTOR_TYPE, help="板块类型，默认行业资金流。")
    parser.add_argument("--fetch-attempts", type=int, default=1, help="每次 collector 内部 AKShare 尝试次数，默认 1，最大 3。")
    parser.add_argument("--force", action="store_true", help="传递给 collector：允许重复记录仍写入。")
    parser.add_argument("--quiet", action="store_true", help="减少输出。")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出 session summary。")
    return parser


def _now_iso(now_fn: Callable[[], datetime] | None = None) -> str:
    if now_fn is not None:
        value = now_fn()
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.isoformat()
            return value.isoformat()
    return datetime.now().astimezone().isoformat()


def _collector_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        dry_run=bool(args.dry_run),
        output_dir=args.output_dir,
        force=bool(args.force),
        quiet=True,
        no_network=bool(args.no_network),
        no_log=bool(args.no_log),
        log_path=args.log_path,
        sector_type=args.sector_type,
        fetch_attempts=max(1, min(int(args.fetch_attempts or 1), 3)),
    )


def _summarize_runs(
    *,
    session_id: str,
    started_at: str,
    finished_at: str,
    requested_runs: int,
    runs: list[dict],
    interrupted: bool = False,
    final_status: str | None = None,
    policy_status: str | None = None,
    policy_decision: dict | None = None,
) -> dict:
    status_counts = Counter(str(run.get("status") or "unknown") for run in runs)
    error_counts = Counter(str(run.get("error_category") or "") for run in runs if run.get("error_category"))
    success_count = sum(status_counts.get(status, 0) for status in {"success"})
    dry_run_count = sum(status_counts.get(status, 0) for status in {"dry_run"})
    duplicate_count = sum(status_counts.get(status, 0) for status in {"duplicate_skipped"})
    failure_count = sum(status_counts.get(status, 0) for status in FAILURE_STATUSES)
    created_paths = [
        str(run.get("output_file"))
        for run in runs
        if run.get("status") == "success" and run.get("output_file")
    ]
    latest_success_time = None
    for run in reversed(runs):
        if run.get("status") == "success":
            latest_success_time = run.get("captured_time") or run.get("trade_date")
            break
    if final_status is None:
        if interrupted:
            final_status = "interrupted"
        elif not runs and policy_status:
            final_status = "blocked_by_policy"
        elif success_count:
            final_status = "success"
        elif dry_run_count and not failure_count:
            final_status = "dry_run_completed"
        elif failure_count:
            final_status = "completed_with_failures"
        elif duplicate_count:
            final_status = "duplicate_skipped"
        else:
            final_status = "completed"
    return {
        "session_id": session_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "requested_runs": requested_runs,
        "attempted_runs": len(runs),
        "success_count": int(success_count),
        "dry_run_count": int(dry_run_count),
        "duplicate_skipped_count": int(duplicate_count),
        "failure_count": int(failure_count),
        "status_counts": dict(status_counts),
        "error_category_counts": dict(error_counts),
        "latest_success_time": latest_success_time,
        "created_snapshot_paths": created_paths,
        "interrupted": bool(interrupted),
        "final_status": final_status,
        "policy_status": policy_status,
        "policy_decision": policy_decision or {},
        "runs": runs,
    }


def run_collection_session(
    args: argparse.Namespace,
    collector_fn: Callable[[argparse.Namespace], dict] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> dict:
    collector_fn = collector_fn or run_collector
    sleep_fn = sleep_fn or time.sleep
    max_runs = max(1, min(int(args.max_runs or 1), 100))
    interval = max(0.0, float(args.interval_seconds or 0))
    session_id = str(uuid.uuid4())
    started_at = _now_iso(now_fn)
    runs: list[dict] = []
    policy_status = None
    policy_decision: dict | None = None
    interrupted = False
    try:
        for index in range(max_runs):
            if getattr(args, "respect_session", True):
                metrics = build_ingestion_metrics(log_path=args.log_path)
                policy_decision = decide_collection_eligibility(
                    get_default_collection_policy(),
                    now=now_fn() if now_fn else None,
                    latest_success_at=metrics.get("latest_success_at"),
                    attempts_in_active_session=len(runs),
                )
                policy_status = policy_decision.get("policy_status")
                if not policy_decision.get("eligible"):
                    break
            else:
                policy_status = "ignored"
                policy_decision = {
                    "eligible": True,
                    "policy_status": "ignored",
                    "policy_reason": "--ignore-session 已跳过本地观察窗口判断。",
                }

            result = collector_fn(_collector_args(args))
            slim_result = {
                "run_index": index + 1,
                "status": result.get("status"),
                "error_category": result.get("error_category"),
                "row_count": result.get("row_count"),
                "written_rows": result.get("written_rows"),
                "trade_date": result.get("trade_date"),
                "captured_time": result.get("captured_time"),
                "output_file": result.get("output_file"),
                "write_status": result.get("write_status"),
                "contract_label": result.get("contract_label"),
                "quality_label": result.get("quality_label"),
                "provider": result.get("provider"),
                "api_name": result.get("api_name"),
                "schema_fingerprint": result.get("schema_fingerprint"),
                "normalization_status": result.get("normalization_status"),
                "message": result.get("message"),
                "warnings": list(result.get("warnings") or [])[:5],
                "errors": list(result.get("errors") or [])[:5],
            }
            runs.append(slim_result)
            status = str(result.get("status") or "")
            if getattr(args, "stop_on_success", False) and status in SUCCESS_LIKE_STATUSES:
                break
            if getattr(args, "stop_on_contract_error", False) and status == "contract_error":
                break
            if index < max_runs - 1 and interval > 0:
                sleep_fn(interval)
    except KeyboardInterrupt:
        interrupted = True
    finished_at = _now_iso(now_fn)
    return _summarize_runs(
        session_id=session_id,
        started_at=started_at,
        finished_at=finished_at,
        requested_runs=max_runs,
        runs=runs,
        interrupted=interrupted,
        policy_status=policy_status,
        policy_decision=policy_decision,
    )


def _print_summary(summary: dict, quiet: bool = False) -> None:
    if quiet:
        return
    print("Collection session summary")
    for key in (
        "session_id",
        "started_at",
        "finished_at",
        "requested_runs",
        "attempted_runs",
        "success_count",
        "dry_run_count",
        "duplicate_skipped_count",
        "failure_count",
        "final_status",
        "policy_status",
        "latest_success_time",
    ):
        print(f"  {key}: {summary.get(key)}")
    print(f"  status_counts: {summary.get('status_counts')}")
    print(f"  error_category_counts: {summary.get('error_category_counts')}")
    for run in summary.get("runs", []):
        print(
            "  run "
            f"{run.get('run_index')}: status={run.get('status')} "
            f"rows={run.get('row_count')} written={run.get('written_rows')} "
            f"message={run.get('message')}"
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_collection_session(args)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_summary(summary, args.quiet)
    return 1 if summary.get("final_status") == "runner_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
