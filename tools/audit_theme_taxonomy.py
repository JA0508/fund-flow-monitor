from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.theme_taxonomy import get_theme_names, load_theme_taxonomy  # noqa: E402
from src.theme_taxonomy_audit import (  # noqa: E402
    build_cross_theme_overlap_audit,
    build_source_universe_coverage_audit,
    build_taxonomy_audit_report,
    build_theme_calibration_report,
    validate_taxonomy_audit_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit theme taxonomy semantics without network or writes.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON audit report.")
    parser.add_argument("--source-mode", default="SAMPLE", choices=["SAMPLE", "REAL"], help="Source universe to audit.")
    parser.add_argument("--data-dir", default=None, help="Optional CSV directory override.")
    parser.add_argument("--theme", default=None, help="Optional theme calibration report.")
    parser.add_argument("--overlap", action="store_true", help="Print cross-theme overlap rows.")
    parser.add_argument("--coverage", action="store_true", help="Print source-universe coverage summary.")
    parser.add_argument("--top-overlaps", type=int, default=8, help="Number of overlap pairs to print.")
    return parser


def _json_ready(value):
    if hasattr(value, "to_dict"):
        return value.to_dict(orient="records")
    return value


def _print_summary(report: dict) -> None:
    validation = report.get("validation", {})
    coverage = report.get("coverage", {})
    print("Theme taxonomy audit")
    print(f"  taxonomy: {report.get('taxonomy_name')} {report.get('taxonomy_version')}")
    print(f"  source_mode: {report.get('source_mode')}")
    print(f"  themes: {report.get('theme_count')}")
    print(f"  member_assignments: {report.get('member_assignment_count')}")
    print(f"  unique_canonical_members: {report.get('unique_canonical_member_count')}")
    print(f"  validation errors/warnings: {validation.get('error_count')} / {validation.get('warning_count')}")
    print(f"  reused_members: {report.get('reused_members') or {}}")
    print(f"  reused_strict_representatives: {report.get('reused_strict_representatives') or {}}")
    print(
        "  coverage: "
        f"{coverage.get('mapped_source_row_count')}/{coverage.get('unique_source_row_count')} "
        f"({coverage.get('mapping_coverage_rate')})"
    )
    print(f"  ambiguous_source_rows: {coverage.get('ambiguous_source_row_count')}")
    print(f"  unmapped_source_rows: {coverage.get('unmapped_source_row_count')}")
    print("  note: coverage is taxonomy-to-source-universe matching coverage, not an investment-quality score.")


def _print_coverage(coverage: dict) -> None:
    print("Coverage audit")
    print(f"  source_mode: {coverage.get('source_mode')}")
    print(f"  latest_trade_date: {coverage.get('latest_trade_date')}")
    print(f"  denominator: {coverage.get('denominator_note')}")
    print(f"  total unique source rows: {coverage.get('unique_source_row_count')}")
    print(f"  mapped: {coverage.get('mapped_source_row_count')}")
    print(f"  ambiguous: {coverage.get('ambiguous_source_row_count')}")
    print(f"  unmapped: {coverage.get('unmapped_source_row_count')}")
    print(f"  canonical_exact: {coverage.get('canonical_exact_match_count')}")
    print(f"  alias_match: {coverage.get('alias_match_count')}")
    print(f"  themes represented: {', '.join(coverage.get('themes_represented') or []) or '<none>'}")
    for row in (coverage.get("ambiguous_source_rows") or [])[:8]:
        print(f"  ambiguous row: {row.get('sector_name')} -> {row.get('candidate_themes')}")
    for row in (coverage.get("unmapped_source_rows") or [])[:8]:
        print(f"  unmapped row: {row.get('sector_name')}")


def _print_overlap(rows: list[dict], top_n: int) -> None:
    print("Cross-theme overlap")
    for row in rows[: max(0, top_n)]:
        shared = "，".join(row.get("shared_members") or []) or "<none>"
        print(
            "  - "
            f"{row.get('theme_left')} × {row.get('theme_right')} | "
            f"state={row.get('overlap_state')} | "
            f"jaccard={row.get('jaccard_overlap')} | shared={shared}"
        )


def _print_theme(theme: str, calibration_rows: list[dict]) -> None:
    row = next((item for item in calibration_rows if item.get("theme_name") == theme), None)
    if not row:
        print(f"Theme calibration: unknown theme {theme}")
        return
    print(f"Theme calibration: {theme}")
    print(f"  fingerprint: {str(row.get('theme_definition_fingerprint') or '')[:16]}")
    print(f"  member/core/related/strict: {row.get('member_count')} / {row.get('core_count')} / {row.get('related_count')} / {row.get('strict_representative_count')}")
    print(f"  matched/unmatched: {row.get('matched_member_count')} / {row.get('unmatched_member_count')}")
    print(f"  provenance: {row.get('member_provenance_counts')}")
    print(f"  highest_overlap_neighbors: {row.get('highest_overlap_neighbors')}")
    if row.get("warnings"):
        print("  warnings:")
        for warning in row.get("warnings")[:8]:
            print(f"    - {warning}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    taxonomy = load_theme_taxonomy()
    report = build_taxonomy_audit_report(taxonomy, source_mode=args.source_mode, data_dir=args.data_dir)
    overlap_df = build_cross_theme_overlap_audit(taxonomy)
    overlap_rows = (
        overlap_df.sort_values(["jaccard_overlap", "shared_member_count"], ascending=False).to_dict(orient="records")
        if not overlap_df.empty
        else []
    )
    calibration_df = build_theme_calibration_report(taxonomy, source_mode=args.source_mode, data_dir=args.data_dir)
    calibration_rows = calibration_df.to_dict(orient="records") if not calibration_df.empty else []
    if args.theme and args.theme not in set(get_theme_names(taxonomy)):
        report.setdefault("warnings", []).append(f"未知主题：{args.theme}")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        _print_summary(report)
        if args.coverage:
            _print_coverage(report.get("coverage", {}))
        if args.overlap:
            _print_overlap(overlap_rows, args.top_overlaps)
        if args.theme:
            _print_theme(args.theme, calibration_rows)
    forbidden = validate_taxonomy_audit_text(json.dumps(report, ensure_ascii=False, default=str))
    if forbidden:
        print(f"forbidden_hits: {forbidden}", file=sys.stderr)
        return 2
    if args.theme and args.theme not in set(get_theme_names(taxonomy)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
