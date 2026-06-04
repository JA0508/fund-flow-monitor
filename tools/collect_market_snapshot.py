from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DEFAULT_SECTOR_TYPE  # noqa: E402
from src.data_source import fetch_sector_flow  # noqa: E402
from src.snapshot_quality import audit_snapshot_dataframe  # noqa: E402
from src.storage import append_snapshot_safely, get_snapshot_output_path  # noqa: E402
from src.transform import normalize_sector_flow  # noqa: E402
from src.utils import get_china_now  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="手动采集一次 A 股行业资金流快照并写入本地 CSV。不会循环运行。",
    )
    parser.add_argument("--dry-run", action="store_true", help="只抓取并检查，不写入文件。")
    parser.add_argument("--output-dir", default="data/ticks", help="真实缓存输出目录，默认 data/ticks。")
    parser.add_argument("--force", action="store_true", help="允许重复 captured_time + sector_name 仍写入。")
    parser.add_argument("--quiet", action="store_true", help="减少输出。")
    parser.add_argument("--no-network", action="store_true", help="不访问 AKShare，仅检查脚本参数和导入。")
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


def collect_once(args: argparse.Namespace) -> dict:
    if args.no_network:
        return {
            "fetch_status": "skipped_no_network",
            "row_count": 0,
            "captured_time": None,
            "output_file": None,
            "duplicate_detected": False,
            "write_status": "not_run",
            "quality_label": "未采集",
            "warnings": ["--no-network 模式不会访问 AKShare，也不会写入文件。"],
            "errors": [],
        }

    now = get_china_now()
    try:
        raw_df = fetch_sector_flow(sector_type=args.sector_type, indicator="今日")
        snapshot = normalize_sector_flow(raw_df, sector_type=args.sector_type, captured_at=now)
    except RuntimeError as exc:
        return {
            "fetch_status": "error",
            "row_count": 0,
            "captured_time": None,
            "output_file": None,
            "duplicate_detected": False,
            "write_status": "not_written",
            "quality_label": "无可用数据",
            "warnings": [],
            "errors": [str(exc)],
        }

    data_date = snapshot["trade_date"].iloc[0] if not snapshot.empty and "trade_date" in snapshot.columns else now.strftime("%Y-%m-%d")
    captured_time = snapshot["captured_time"].iloc[0] if not snapshot.empty and "captured_time" in snapshot.columns else None
    output_file = get_snapshot_output_path(data_date=str(data_date), directory=args.output_dir)
    quality = audit_snapshot_dataframe(snapshot, source_label="manual_collect", file_path=output_file)
    duplicate_detected = _detect_existing_duplicate(snapshot, output_file)

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

    return {
        "fetch_status": "success",
        "row_count": int(len(snapshot)),
        "captured_time": captured_time,
        "output_file": output_file,
        "duplicate_detected": duplicate_detected,
        "write_status": write_result.get("write_status", "dry_run"),
        "quality_label": quality.get("quality_label", "--"),
        "warnings": list(quality.get("warnings") or []) + list(write_result.get("warnings") or []),
        "errors": list(quality.get("errors") or []) + list(write_result.get("errors") or []),
        "written_rows": int(write_result.get("written_rows", 0) or 0),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = collect_once(args)
    _print("本地市场快照手动采集结果", args.quiet)
    for key in ("fetch_status", "row_count", "captured_time", "output_file", "duplicate_detected", "write_status", "quality_label", "written_rows"):
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
    return 1 if errors and result.get("fetch_status") != "skipped_no_network" else 0


if __name__ == "__main__":
    raise SystemExit(main())
