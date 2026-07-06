from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.theme_observation_evidence import (  # noqa: E402
    build_theme_evidence_contribution_table,
    resolve_theme_observation_evidence,
    validate_theme_evidence_text,
)
from src.theme_pool import THEME_MODE_LABELS  # noqa: E402
from src.theme_taxonomy import get_theme_names, load_theme_taxonomy  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect local theme observation evidence without network or writes.")
    parser.add_argument("--theme", required=True, help="Theme name configured in theme_taxonomy.json.")
    parser.add_argument("--mode", default="strict_representative", choices=list(THEME_MODE_LABELS.keys()))
    parser.add_argument("--source-mode", default="SAMPLE", choices=["SAMPLE", "REAL"])
    parser.add_argument("--date", default=None, help="Optional trade date, e.g. 2026-01-16.")
    parser.add_argument("--data-dir", default=None, help="Optional CSV directory override.")
    parser.add_argument("--json", action="store_true", help="Print full compact JSON evidence.")
    parser.add_argument("--members", action="store_true", help="Print member contribution table.")
    parser.add_argument("--trace", action="store_true", help="Print readable trace.")
    return parser


def inspect_theme_evidence(
    theme: str,
    mode: str = "strict_representative",
    source_mode: str = "SAMPLE",
    date: str | None = None,
    data_dir: str | None = None,
) -> dict:
    taxonomy = load_theme_taxonomy()
    known = set(get_theme_names(taxonomy))
    if theme not in known:
        return {
            "evidence_available": False,
            "theme_name": theme,
            "source_mode": source_mode,
            "warnings": [f"未知主题：{theme}。可用主题：{', '.join(sorted(known))}"],
        }
    return resolve_theme_observation_evidence(
        theme_name=theme,
        source_mode=source_mode,
        theme_mode=mode,
        trade_date=date,
        data_dir=data_dir,
        taxonomy=taxonomy,
    )


def _compact_json(evidence: dict) -> str:
    compact = dict(evidence)
    compact.pop("canonical_theme_row", None)
    if "member_traces" in compact:
        compact["member_traces"] = compact["member_traces"][:30]
    return json.dumps(compact, ensure_ascii=False, indent=2)


def _print_trace(evidence: dict) -> None:
    print("Theme observation evidence")
    print(f"  theme: {evidence.get('theme_name')}")
    print(f"  source_mode: {evidence.get('source_mode')}")
    print(f"  mode: {evidence.get('observation_mode')} / {evidence.get('observation_mode_label')}")
    print(f"  date/time: {evidence.get('as_of_trade_date')} / {evidence.get('as_of_captured_time')}")
    print(f"  taxonomy_fingerprint: {str(evidence.get('taxonomy_fingerprint') or '')[:16]}")
    print(f"  theme_definition_fingerprint: {str(evidence.get('theme_definition_fingerprint') or '')[:16]}")
    print(f"  matched/used/unmatched: {evidence.get('matched_member_count')} / {evidence.get('used_member_count')} / {evidence.get('unmatched_member_count')}")
    print(f"  aggregation_method: {evidence.get('aggregation_method')}")
    print(f"  aggregate_value: {evidence.get('aggregate_value')}")
    print(f"  derived_state: {evidence.get('derived_state')}")
    data = evidence.get("data_evidence", {})
    print(f"  history_span_state: {data.get('history_span_state')}")
    print(f"  intraday_depth_state: {data.get('intraday_depth_state')}")
    print(f"  coverage_consistency_state: {data.get('coverage_consistency_state')}")
    print(f"  schema_consistent: {data.get('schema_consistent')}")
    warnings = evidence.get("warnings") or []
    if warnings:
        print("  warnings:")
        for warning in warnings:
            print(f"    - {warning}")


def _display(value) -> str:
    text = "" if value is None else str(value)
    return "--" if text.lower() == "nan" or not text else text


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evidence = inspect_theme_evidence(
        theme=args.theme,
        mode=args.mode,
        source_mode=args.source_mode,
        date=args.date,
        data_dir=args.data_dir,
    )
    forbidden = validate_theme_evidence_text(_compact_json(evidence))
    if args.json:
        print(_compact_json(evidence))
    else:
        _print_trace(evidence)
    if args.members:
        table = build_theme_evidence_contribution_table(evidence)
        print("Member contribution table")
        if table.empty:
            print("  <empty>")
        else:
            for row in table.to_dict(orient="records"):
                print(
                    "  - "
                    f"{_display(row.get('member_name'))} | canonical={_display(row.get('canonical_member'))} | role={_display(row.get('member_role'))} | "
                    f"matched_by={_display(row.get('matched_by') or row.get('match_type'))} | "
                    f"source_row={_display(row.get('matched_source_row'))} | included={row.get('included')} | "
                    f"value={_display(row.get('input_value'))} | method={_display(row.get('mapping_method'))} | "
                    f"reason={_display(row.get('exclusion_reason'))}"
                )
    if args.trace and args.json:
        _print_trace(evidence)
    if forbidden:
        print(f"forbidden_hits: {forbidden}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
