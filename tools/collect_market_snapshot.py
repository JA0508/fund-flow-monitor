from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DEFAULT_SECTOR_TYPE  # noqa: E402
from src.data_source import fetch_sector_flow  # noqa: E402
from src.data_contracts import validate_real_snapshot_dataframe  # noqa: E402
from src.snapshot_quality import audit_snapshot_dataframe  # noqa: E402
from src.storage import append_snapshot_safely, get_snapshot_output_path  # noqa: E402
from src.transform import normalize_sector_flow  # noqa: E402
from src.utils import get_china_now  # noqa: E402

DEFAULT_AUDIT_LOG_PATH = "data/logs/collector_runs.jsonl"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="手动采集一次 A 股行业资金流快照并写入本地 CSV。不会循环运行。",
    )
    parser.add_argument("--dry-run", action="store_true", help="只抓取并检查，不写入文件。")
    parser.add_argument("--output-dir", default="data/ticks", help="真实缓存输出目录，默认 data/ticks。")
    parser.add_argument("--force", action="store_true", help="允许重复 captured_time + sector_name 仍写入。")
    parser.add_argument("--quiet", action="store_true", help="减少输出。")
    parser.add_argument("--no-network", action="store_true", help="不访问 AKShare，仅检查脚本参数和导入。")
    parser.add_argument("--no-log", action="store_true", help="不写入采集审计日志。")
    parser.add_argument("--log-path", default=DEFAULT_AUDIT_LOG_PATH, help="采集审计 JSONL 路径，默认 data/logs/collector_runs.jsonl。")
    parser.add_argument("--sector-type", default=DEFAULT_SECTOR_TYPE, help="板块类型，默认行业资金流。")
    return parser


def _print(message: str, quiet: bool = False) -> None:
    if not quiet:
        print(message)


def _detect_existing_duplicate(snapshot: pd.DataFrame, output_file: str) -> bool:
    path = Path(output_file)
    if snapshot.empty or not path.exists():
        return False
    try:
        existing = pd.read_csv(path, dtype={"sector_code": str})
    except Exception:
        return False
    keys = [column for column in ("captured_time", "sector_type", "sector_name") if column in snapshot.columns and column in existing.columns]
    if not keys:
        return False
    existing_keys = set(map(tuple, existing[keys].astype(str).to_numpy()))
    incoming_keys = snapshot[keys].astype(str).apply(tuple, axis=1)
    return bool(incoming_keys.isin(existing_keys).any())


def _classify_fetch_exception(exc: Exception) -> tuple[str, str]:
    message = str(exc)
    if "空数据" in message or "empty" in message.lower():
        return "empty_fetch", "empty_fetch"
    return "fetch_error", "fetch_error"


def _build_message(result: dict) -> str:
    status = result.get("status")
    if status == "success":
        return "真实快照已采集并写入本地 CSV 缓存。"
    if status == "dry_run":
        return "dry-run 已完成抓取和校验，未写入本地 CSV。"
    if status == "no_network":
        return "--no-network 已跳过 AKShare 访问和 CSV 写入。"
    if status == "duplicate_skipped":
        return "检测到重复 captured_time + sector 记录，本次未追加重复行。"
    if status == "empty_fetch":
        return "AKShare 返回空数据或规范化后无可用记录。"
    if status == "contract_error":
        return "真实快照未通过轻量数据契约，已停止写入。"
    if status == "write_error":
        return "真实快照写入本地 CSV 时失败。"
    if status == "fetch_error":
        return "AKShare 抓取失败，未写入本地 CSV。"
    return "采集流程结束。"


def _finalize_result(result: dict) -> dict:
    result.setdefault("status", "success")
    result.setdefault("error_category", None)
    result.setdefault("message", _build_message(result))
    return result


def collect_once(args: argparse.Namespace) -> dict:
    if args.no_network:
        return _finalize_result({
            "status": "no_network",
            "error_category": None,
            "fetch_status": "skipped_no_network",
            "row_count": 0,
            "trade_date": None,
            "captured_time": None,
            "output_file": None,
            "source": None,
            "provider": None,
            "api_name": None,
            "data_mode": None,
            "duplicate_detected": False,
            "write_status": "not_run",
            "contract_label": "未运行",
            "contract_ok": None,
            "quality_label": "未采集",
            "warnings": ["--no-network 模式不会访问 AKShare，也不会写入文件。"],
            "errors": [],
        })

    now = get_china_now()
    try:
        raw_df = fetch_sector_flow(sector_type=args.sector_type, indicator="今日")
        snapshot = normalize_sector_flow(raw_df, sector_type=args.sector_type, captured_at=now)
    except Exception as exc:
        status, error_category = _classify_fetch_exception(exc)
        return _finalize_result({
            "status": status,
            "error_category": error_category,
            "fetch_status": "error",
            "row_count": 0,
            "trade_date": None,
            "captured_time": None,
            "output_file": None,
            "source": None,
            "provider": None,
            "api_name": None,
            "data_mode": None,
            "duplicate_detected": False,
            "write_status": "not_written",
            "contract_label": "未运行",
            "contract_ok": False,
            "quality_label": "无可用数据",
            "warnings": [],
            "errors": [str(exc)],
        })

    data_date = snapshot["trade_date"].iloc[0] if not snapshot.empty and "trade_date" in snapshot.columns else now.strftime("%Y-%m-%d")
    captured_time = snapshot["captured_time"].iloc[0] if not snapshot.empty and "captured_time" in snapshot.columns else None
    output_file = get_snapshot_output_path(data_date=str(data_date), directory=args.output_dir)
    quality = audit_snapshot_dataframe(snapshot, source_label="manual_collect", file_path=output_file)
    contract = validate_real_snapshot_dataframe(snapshot, context=f"collect:{args.sector_type}")
    duplicate_detected = _detect_existing_duplicate(snapshot, output_file)
    contract_errors = list(contract.get("errors") or [])
    quality_errors = list(quality.get("errors") or [])

    if snapshot.empty:
        return _finalize_result({
            "status": "empty_fetch",
            "error_category": "empty_fetch",
            "fetch_status": "success",
            "row_count": 0,
            "trade_date": data_date,
            "captured_time": captured_time,
            "output_file": output_file,
            "source": "AKShare / Eastmoney",
            "provider": "AKShare / Eastmoney",
            "api_name": "stock_sector_fund_flow_rank",
            "data_mode": "REAL",
            "duplicate_detected": duplicate_detected,
            "write_status": "not_written",
            "contract_label": contract.get("contract_label", "--"),
            "contract_ok": False,
            "quality_label": quality.get("quality_label", "--"),
            "warnings": list(contract.get("warnings") or []) + list(quality.get("warnings") or []),
            "errors": contract_errors + quality_errors + ["规范化后没有可写入的真实快照行。"],
            "written_rows": 0,
        })

    if not contract.get("contract_ok", False) or contract_errors:
        return _finalize_result({
            "status": "contract_error",
            "error_category": "contract_error",
            "fetch_status": "success",
            "row_count": int(len(snapshot)),
            "trade_date": data_date,
            "captured_time": captured_time,
            "output_file": output_file,
            "source": snapshot["source"].iloc[0] if "source" in snapshot.columns else "AKShare / Eastmoney",
            "provider": snapshot["provider"].iloc[0] if "provider" in snapshot.columns else "AKShare / Eastmoney",
            "api_name": snapshot["api_name"].iloc[0] if "api_name" in snapshot.columns else "stock_sector_fund_flow_rank",
            "data_mode": snapshot["data_mode"].iloc[0] if "data_mode" in snapshot.columns else "REAL",
            "duplicate_detected": duplicate_detected,
            "write_status": "not_written",
            "contract_label": contract.get("contract_label", "--"),
            "contract_ok": False,
            "quality_label": quality.get("quality_label", "--"),
            "warnings": list(contract.get("warnings") or []) + list(quality.get("warnings") or []),
            "errors": contract_errors + quality_errors,
            "written_rows": 0,
        })

    write_result = {
        "write_status": "dry_run",
        "warnings": [],
        "errors": [],
        "written_rows": 0,
    }
    if not args.dry_run:
        write_result = append_snapshot_safely(
            snapshot,
            output_file,
            dedupe_keys=["captured_time", "sector_type", "sector_name"],
            force=args.force,
        )
        duplicate_detected = bool(write_result.get("duplicate_detected", duplicate_detected))

    write_status = write_result.get("write_status", "dry_run")
    write_errors = list(write_result.get("errors") or [])
    if args.dry_run:
        status = "dry_run"
        error_category = None
    elif write_errors or write_status in {"error", "blocked"}:
        status = "write_error"
        error_category = "write_error"
    elif write_status == "skipped_duplicate":
        status = "duplicate_skipped"
        error_category = None
    else:
        status = "success"
        error_category = None

    return _finalize_result({
        "status": status,
        "error_category": error_category,
        "fetch_status": "success",
        "row_count": int(len(snapshot)),
        "trade_date": data_date,
        "captured_time": captured_time,
        "output_file": output_file,
        "source": snapshot["source"].iloc[0] if "source" in snapshot.columns and not snapshot.empty else "AKShare / Eastmoney",
        "provider": snapshot["provider"].iloc[0] if "provider" in snapshot.columns and not snapshot.empty else "AKShare / Eastmoney",
        "api_name": snapshot["api_name"].iloc[0] if "api_name" in snapshot.columns and not snapshot.empty else "stock_sector_fund_flow_rank",
        "data_mode": snapshot["data_mode"].iloc[0] if "data_mode" in snapshot.columns and not snapshot.empty else "REAL",
        "duplicate_detected": duplicate_detected,
        "write_status": write_result.get("write_status", "dry_run"),
        "contract_label": contract.get("contract_label", "--"),
        "contract_ok": bool(contract.get("contract_ok")),
        "quality_label": quality.get("quality_label", "--"),
        "warnings": list(contract.get("warnings") or []) + list(quality.get("warnings") or []) + list(write_result.get("warnings") or []),
        "errors": contract_errors + quality_errors + write_errors,
        "written_rows": int(write_result.get("written_rows", 0) or 0),
    })


def build_audit_log_entry(result: dict) -> dict:
    return {
        "timestamp": get_china_now().isoformat(),
        "status": result.get("status"),
        "rows": int(result.get("row_count", 0) or 0),
        "written_rows": int(result.get("written_rows", 0) or 0),
        "captured_time": result.get("captured_time"),
        "trade_date": result.get("trade_date"),
        "source": result.get("source"),
        "provider": result.get("provider"),
        "api_name": result.get("api_name"),
        "data_mode": result.get("data_mode"),
        "output_path": result.get("output_file"),
        "contract_label": result.get("contract_label"),
        "quality_label": result.get("quality_label"),
        "error_category": result.get("error_category"),
        "message": result.get("message"),
    }


def append_audit_log(entry: dict, log_path: str = DEFAULT_AUDIT_LOG_PATH) -> dict:
    path = Path(log_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception as exc:
        return {
            "log_status": "error",
            "log_path": str(path),
            "warnings": [],
            "errors": [f"审计日志写入失败：{exc}"],
        }
    return {
        "log_status": "written",
        "log_path": str(path),
        "warnings": [],
        "errors": [],
    }


def run_collector(args: argparse.Namespace) -> dict:
    result = collect_once(args)
    if getattr(args, "no_log", False):
        result["log_status"] = "disabled"
        result["log_path"] = None
        return result
    log_path = getattr(args, "log_path", DEFAULT_AUDIT_LOG_PATH) or DEFAULT_AUDIT_LOG_PATH
    log_result = append_audit_log(build_audit_log_entry(result), log_path)
    result["log_status"] = log_result.get("log_status")
    result["log_path"] = log_result.get("log_path")
    result["warnings"] = list(result.get("warnings") or []) + list(log_result.get("warnings") or [])
    result["errors"] = list(result.get("errors") or []) + list(log_result.get("errors") or [])
    if log_result.get("errors") and result.get("status") in {"success", "dry_run", "duplicate_skipped", "no_network"}:
        result["status"] = "write_error"
        result["error_category"] = "audit_log_error"
        result["message"] = "采集流程完成，但审计日志写入失败。"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_collector(args)
    _print("本地市场快照手动采集结果", args.quiet)
    for key in (
        "status",
        "fetch_status",
        "row_count",
        "trade_date",
        "captured_time",
        "output_file",
        "source",
        "provider",
        "api_name",
        "data_mode",
        "duplicate_detected",
        "write_status",
        "contract_label",
        "quality_label",
        "written_rows",
        "log_status",
        "log_path",
        "error_category",
        "message",
    ):
        if key in result:
            _print(f"{key}: {result.get(key)}", args.quiet)
    warnings = result.get("warnings") or []
    errors = result.get("errors") or []
    if warnings:
        _print("warnings:", args.quiet)
        for warning in warnings:
            _print(f"  - {warning}", args.quiet)
    if errors:
        _print("errors:", args.quiet)
        for error in errors:
            _print(f"  - {error}", args.quiet)
    if result.get("status") in {"fetch_error", "empty_fetch", "contract_error", "write_error"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
