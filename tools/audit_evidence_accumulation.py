from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evidence_accumulation import (  # noqa: E402
    DEFAULT_ACQUISITION_CELL_MINUTES,
    build_evidence_accumulation_report,
    validate_evidence_accumulation_text,
)
from src.sample_data import SAMPLE_DIR  # noqa: E402


def _default_data_dir(source_mode: str) -> str:
    return SAMPLE_DIR if str(source_mode or "").upper() == "SAMPLE" else "data/ticks"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit physical capture acquisition coverage without network or writes.")
    parser.add_argument("--source-mode", "--source", choices=["SAMPLE", "REAL"], default="SAMPLE")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--trade-date", default=None)
    parser.add_argument("--cell-minutes", type=int, default=DEFAULT_ACQUISITION_CELL_MINUTES)
    parser.add_argument("--json", action="store_true")
    return parser


def print_report(report: dict) -> None:
    print("Evidence accumulation audit")
    print(f"  source_mode: {report.get('source_mode')}")
    print(f"  data_dir: {report.get('data_dir')}")
    print(f"  network_used: {report.get('network_used')}")
    print(f"  acquisition_frame_id: {report.get('acquisition_frame_id')}")
    print(f"  acquisition_cell_minutes: {report.get('acquisition_cell_minutes')}")
    print(f"  physical captures: {report.get('physical_capture_event_count', 0)}")
    print(f"  qualified captures: {report.get('qualified_capture_event_count', 0)}")
    print(f"  excluded captures: {report.get('excluded_capture_event_count', 0)}")
    print(f"  represented dates: {report.get('represented_dates', [])}")
    print(
        "  covered cells: "
        f"{report.get('coverage_numerator', 0)} / {report.get('coverage_denominator', 0)}"
    )
    print(f"  coverage share: {report.get('qualified_acquisition_cell_coverage_share', 0.0)}")
    print(f"  missing cells by date: {report.get('missing_cells_by_date', {})}")
    print(f"  covered cells by session: {report.get('covered_cells_by_session', {})}")
    print(f"  multi-capture cells: {report.get('multi_capture_cell_count', 0)}")
    print(f"  off-frame captures: {report.get('off_frame_capture_count', 0)}")
    print(f"  provider resolution counts: {report.get('provider_contract_resolution_counts', {})}")
    print(f"  marginal contributions: {report.get('marginal_contribution_counts', {})}")
    print(f"  exclusion reasons: {report.get('excluded_reason_counts', {})}")
    for warning in report.get("warnings", []):
        print(f"  warning: {warning}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = str(args.source_mode or "SAMPLE").upper()
    data_dir = args.data_dir or _default_data_dir(source)
    report = build_evidence_accumulation_report(
        source_mode=source,
        data_dir=data_dir,
        cell_minutes=args.cell_minutes,
        trade_date=args.trade_date,
    )
    text = json.dumps(report, ensure_ascii=False, sort_keys=True)
    hits = validate_evidence_accumulation_text(text)
    if hits:
        print(f"Forbidden evidence accumulation wording detected: {hits}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
