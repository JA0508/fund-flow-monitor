from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.history_evidence import (  # noqa: E402
    build_coverage_matrix,
    build_historical_coverage_summary,
    build_snapshot_manifest,
    classify_historical_evidence_readiness,
    resolve_replay_evidence,
    validate_history_evidence_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect local CSV historical evidence without network or writes.")
    parser.add_argument("--data-dir", default="data/ticks", help="CSV snapshot directory to inspect.")
    parser.add_argument("--source-mode", default="REAL", choices=("REAL", "SAMPLE"), help="Evidence source mode label.")
    parser.add_argument("--bucket-minutes", type=int, default=1, help="captured_time bucket size in minutes.")
    parser.add_argument("--date", default=None, help="Optional trade date for replay evidence.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    parser.add_argument("--matrix", action="store_true", help="Print captured_time coverage matrix.")
    return parser


def inspect_history_evidence(
    data_dir: str = "data/ticks",
    source_mode: str = "REAL",
    bucket_minutes: int = 1,
    selected_date: str | None = None,
) -> dict:
    manifest = build_snapshot_manifest(data_dir=data_dir, source_mode=source_mode, bucket_minutes=bucket_minutes)
    summary = build_historical_coverage_summary(manifest)
    readiness = classify_historical_evidence_readiness(summary)
    matrix = build_coverage_matrix(manifest, bucket_minutes=bucket_minutes)
    replay = resolve_replay_evidence(selected_date, manifest, source_mode=source_mode, mode="HISTORY") if selected_date else {}
    text = f"{summary.get('coverage_label', '')} {readiness.get('readiness_label', '')} {readiness.get('readiness_reason', '')}"
    return {
        "data_dir": data_dir,
        "source_mode": source_mode,
        "bucket_minutes": int(bucket_minutes or 1),
        "manifest_row_count": int(len(manifest)),
        "summary": summary,
        "readiness": readiness,
        "matrix_shape": tuple(matrix.shape),
        "matrix": matrix.to_dict(orient="records") if not matrix.empty else [],
        "replay_evidence": replay,
        "forbidden_hits": validate_history_evidence_text(text),
    }


def _print_report(report: dict, include_matrix: bool = False) -> None:
    summary = report.get("summary", {})
    readiness = report.get("readiness", {})
    print("Historical evidence inspection")
    print(f"  data_dir: {report.get('data_dir')}")
    print(f"  source_mode: {report.get('source_mode')}")
    print(f"  manifest_row_count: {report.get('manifest_row_count')}")
    print(f"  coverage_label: {summary.get('coverage_label')}")
    print(f"  readiness_state: {readiness.get('readiness_state')}")
    print(f"  readiness_label: {readiness.get('readiness_label')}")
    print(f"  valid_snapshot_count: {summary.get('valid_snapshot_count')}")
    print(f"  trade_date_count: {summary.get('trade_date_count')}")
    print(f"  date_range: {summary.get('earliest_trade_date')} -> {summary.get('latest_trade_date')}")
    print(f"  schema_consistent: {summary.get('schema_consistent')}")
    print(f"  contract_pass/fail: {summary.get('contract_pass_count')} / {summary.get('contract_fail_count')}")
    print(f"  forbidden_hits: {report.get('forbidden_hits')}")
    replay = report.get("replay_evidence") or {}
    if replay:
        print(f"  replay_date: {replay.get('selected_trade_date')}")
        print(f"  replay_state: {replay.get('evidence_state')}")
        print(f"  replay_time_range: {replay.get('captured_time_start')} -> {replay.get('captured_time_end')}")
    if include_matrix:
        print("  coverage_matrix:")
        for row in report.get("matrix", []):
            print(f"    {row}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = inspect_history_evidence(
        data_dir=args.data_dir,
        source_mode=args.source_mode,
        bucket_minutes=args.bucket_minutes,
        selected_date=args.date,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        _print_report(report, include_matrix=args.matrix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
