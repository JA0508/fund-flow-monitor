from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.theme_dynamics import (  # noqa: E402
    build_scope_divergence_table,
    build_theme_dynamics_evidence,
    build_theme_observation_cube,
    get_bucketed_analytical_observation_grain,
    get_raw_event_observation_grain,
    get_theme_observation_grain,
    normalize_theme_dynamics_mode,
    validate_theme_dynamics_text,
)
from src.theme_pool import THEME_MODE_LABELS  # noqa: E402
from src.theme_taxonomy import get_theme_names, load_theme_taxonomy  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect read-only theme dynamics evidence from local CSV snapshots.")
    parser.add_argument("--theme", required=True, help="Theme name configured in theme_taxonomy.json.")
    parser.add_argument("--source-mode", default="SAMPLE", choices=["SAMPLE", "REAL"])
    parser.add_argument("--mode", default="strict_representative", choices=list(THEME_MODE_LABELS.keys()))
    parser.add_argument("--data-dir", default=None, help="Optional CSV directory override.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON evidence.")
    parser.add_argument("--state-trace", action="store_true", help="Print state transition trace.")
    parser.add_argument("--scope-divergence", action="store_true", help="Print latest aligned scope divergence.")
    parser.add_argument("--member-divergence", action="store_true", help="Print latest member structural divergence.")
    parser.add_argument("--cube", action="store_true", help="Print compact observation cube rows.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum rows to print for cube output.")
    return parser


def _json_safe(value):
    if isinstance(value, pd.DataFrame):
        return value.head(50).to_dict(orient="records")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _compact_evidence(evidence: dict) -> dict:
    compact = _json_safe(evidence)
    # Keep JSON useful but avoid dumping full member raw traces.
    return compact


def inspect_theme_dynamics(
    theme: str,
    source_mode: str = "SAMPLE",
    mode: str = "strict_representative",
    data_dir: str | None = None,
) -> tuple[dict, pd.DataFrame]:
    taxonomy = load_theme_taxonomy()
    known = set(get_theme_names(taxonomy))
    if theme not in known:
        return (
            {
                "dynamics_available": False,
                "theme_name": theme,
                "source_mode": source_mode,
                "warnings": [f"未知主题：{theme}。可用主题：{', '.join(sorted(known))}"],
            },
            pd.DataFrame(),
        )
    cube = build_theme_observation_cube(
        taxonomy=taxonomy,
        source_mode=source_mode,
        data_dir=data_dir,
        calculation_modes=("strict_representative", "representative", "breadth"),
    )
    evidence = build_theme_dynamics_evidence(
        cube,
        theme_name=theme,
        source_mode=source_mode,
        calculation_mode=normalize_theme_dynamics_mode(mode),
        taxonomy=taxonomy,
        data_dir=data_dir,
    )
    return evidence, cube


def _print_header(evidence: dict) -> None:
    collisions = evidence.get("bucket_collision_summary") or {}
    print("Theme dynamics evidence")
    print(f"  theme: {evidence.get('theme_name')}")
    print(f"  source_mode: {evidence.get('source_mode')}")
    print(f"  mode: {evidence.get('calculation_mode')} / {evidence.get('calculation_mode_label')}")
    print(f"  raw event grain: {' × '.join(get_raw_event_observation_grain())}")
    print(f"  analytical grain: {' × '.join(get_bucketed_analytical_observation_grain())}")
    print(f"  compatibility grain alias: {' × '.join(get_theme_observation_grain())}")
    print(f"  dynamics_basis: {evidence.get('dynamics_basis')}")
    print(f"  materialization_policy: {evidence.get('materialization_policy')}")
    print(f"  bucket_minutes: {evidence.get('bucket_minutes')}")
    print(f"  raw_event_observations: {evidence.get('raw_event_observation_count')}")
    print(f"  canonical_observations: {evidence.get('canonical_observation_count')}")
    print(f"  collided_buckets: {collisions.get('collided_bucket_count', 0)}")
    print(f"  extra_events_in_collided_buckets: {collisions.get('extra_events_within_collided_buckets', 0)}")
    print(f"  max_events_per_bucket: {collisions.get('max_events_per_bucket', 0)}")
    print(f"  within_bucket_state_change_buckets: {collisions.get('within_bucket_state_change_count', 0)}")
    print(f"  observations: {evidence.get('observation_count')}")
    print(f"  trade_dates: {evidence.get('trade_date_count')}")
    print(f"  captured_time_buckets: {evidence.get('captured_time_bucket_count')}")
    print(f"  taxonomy_fingerprint: {str(evidence.get('taxonomy_fingerprint') or '')[:16]}")
    print(f"  theme_definition_fingerprint: {str(evidence.get('theme_definition_fingerprint') or '')[:16]}")
    print(f"  lineage_compatible: {evidence.get('lineage_compatible')}")
    warnings = evidence.get("warnings") or []
    if warnings:
        print("  warnings:")
        for item in warnings:
            print(f"    - {item}")


def _print_state_trace(evidence: dict) -> None:
    trace = evidence.get("state_transition_trace") or {}
    print("State transition trace")
    print(f"  state_path: {trace.get('state_path_text') or '--'}")
    print(f"  transition_count: {trace.get('transition_count', 0)}")
    print(f"  unchanged_step_count: {trace.get('unchanged_step_count', 0)}")
    print(f"  state_counts: {trace.get('state_counts', {})}")
    print(
        "  observed_state_shares: "
        f"positive={trace.get('positive_state_share', 0)} "
        f"neutral={trace.get('neutral_state_share', 0)} "
        f"negative={trace.get('negative_state_share', 0)}"
    )
    print(
        "  longest_observed_streaks: "
        f"positive={trace.get('longest_positive_streak', 0)} "
        f"neutral={trace.get('longest_neutral_streak', 0)} "
        f"negative={trace.get('longest_negative_streak', 0)} "
        f"same_state={trace.get('longest_same_state_streak', 0)}"
    )
    print("  denominator: observed share = canonical bucket observations / total canonical bucket observations; not a future-oriented measure.")


def _print_scope_divergence(evidence: dict) -> None:
    scope = evidence.get("scope_divergence_summary") or {}
    print("Scope divergence")
    print(f"  date/time: {scope.get('trade_date') or '--'} / {scope.get('captured_time_bucket') or '--'}")
    print(f"  state: {scope.get('scope_divergence_state') or '--'}")
    print(f"  alignment_status: {scope.get('alignment_status') or '--'}")
    print(f"  aligned_snapshot_id_consistent: {scope.get('aligned_snapshot_id_consistent')}")
    print(f"  compared_snapshot_ids: {scope.get('compared_snapshot_ids') or []}")
    print(f"  available_scope_count: {scope.get('available_scope_count', 0)}")
    for mode in ("strict_representative", "representative", "breadth"):
        print(f"  - {mode}: state={scope.get(f'{mode}_state') or '--'} aggregate={scope.get(f'{mode}_aggregate_value')}")


def _print_member_divergence(evidence: dict) -> None:
    member = evidence.get("latest_member_structural_divergence") or {}
    print("Member structural divergence")
    print(f"  state: {member.get('member_sign_agreement') or member.get('structural_state') or '--'}")
    print(f"  included_member_count: {member.get('included_member_count', 0)}")
    print(
        "  member_counts: "
        f"positive={member.get('positive_member_count', 0)} "
        f"neutral={member.get('neutral_member_count', 0)} "
        f"negative={member.get('negative_member_count', 0)}"
    )
    print(
        "  absolute_value_shares: "
        f"positive={member.get('positive_absolute_value_share', 0)} "
        f"negative={member.get('negative_absolute_value_share', 0)}"
    )


def _print_cube(cube: pd.DataFrame, limit: int) -> None:
    print("Theme observation cube")
    if cube.empty:
        print("  <empty>")
        return
    columns = [
        "theme_name",
        "trade_date",
        "captured_time_bucket",
        "calculation_mode",
        "source_mode",
        "derived_state",
        "aggregate_value",
        "event_count",
        "collision_type",
        "selected_captured_time",
        "observation_id",
    ]
    available = [column for column in columns if column in cube.columns]
    for row in cube[available].head(max(1, int(limit or 20))).to_dict(orient="records"):
        print(
            "  - "
            f"{row.get('theme_name')} | {row.get('trade_date')} {row.get('captured_time_bucket')} | "
            f"{row.get('calculation_mode')} | {row.get('derived_state')} | {row.get('aggregate_value')} | "
            f"{row.get('observation_id')}"
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evidence, cube = inspect_theme_dynamics(
        theme=args.theme,
        source_mode=args.source_mode,
        mode=args.mode,
        data_dir=args.data_dir,
    )
    forbidden = validate_theme_dynamics_text(json.dumps(_compact_evidence(evidence), ensure_ascii=False))
    if args.json:
        print(json.dumps(_compact_evidence(evidence), ensure_ascii=False, indent=2))
    else:
        _print_header(evidence)
        if args.state_trace:
            _print_state_trace(evidence)
        if args.scope_divergence:
            _print_scope_divergence(evidence)
        if args.member_divergence:
            _print_member_divergence(evidence)
        if args.cube:
            _print_cube(cube, args.limit)
    if forbidden:
        print(f"forbidden_hits: {forbidden}", file=sys.stderr)
        return 2
    if not evidence.get("dynamics_available"):
        return 1 if any("未知主题" in str(item) for item in evidence.get("warnings", [])) else 0
    # Build scope table once here to catch accidental structural errors in CLI paths.
    _ = build_scope_divergence_table(cube)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
