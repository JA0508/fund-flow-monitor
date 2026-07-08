from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analytical_robustness import (  # noqa: E402
    CANONICAL_BUCKET_POLICY,
    SUPPORTED_MATERIALIZATION_POLICIES,
    build_robustness_evidence,
    compare_calculation_scope_sensitivity,
    parse_bucket_minutes,
    validate_analytical_robustness_text,
)
from src.theme_dynamics import normalize_theme_dynamics_mode  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only analytical robustness and specification sensitivity audit.")
    parser.add_argument("--source-mode", choices=["SAMPLE", "REAL"], default="SAMPLE")
    parser.add_argument("--theme", default=None)
    parser.add_argument("--pair", default=None, help='Relationship pair as "THEME_A::THEME_B".')
    parser.add_argument("--bucket-minutes", default="1,5,10")
    parser.add_argument("--mode", default="strict_representative")
    parser.add_argument("--all-modes", action="store_true")
    parser.add_argument("--materialization-policies", action="store_true")
    parser.add_argument("--evidence-sufficiency", action="store_true")
    parser.add_argument("--threshold-boundaries", action="store_true")
    parser.add_argument("--date-concentration", action="store_true")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def _json_safe(value):
    if hasattr(value, "to_dict"):
        return value.to_dict(orient="records")
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


def _print_theme(result: dict) -> None:
    evidence = result.get("theme_robustness", {})
    default = evidence.get("default_specification", {})
    print("Analytical robustness evidence")
    print(f"  analysis_type: theme")
    print(f"  theme: {evidence.get('theme_name')}")
    print(f"  source_mode: {evidence.get('source_mode')}")
    print(f"  default specification: {default.get('human_readable')}")
    print(f"  default specification_id: {default.get('specification_id')}")
    print(f"  evaluated specifications: {evidence.get('evaluated_specification_count', 0)}")
    print(f"  headline state path variants: {evidence.get('headline_state_path_variant_count', 0)}")
    print(f"  latest headline state values: {evidence.get('latest_headline_state_values', [])}")
    print(f"  regime signature count range: {evidence.get('regime_signature_count_range', {})}")
    print(f"  episode count range: {evidence.get('episode_count_range', {})}")
    print("  variant table:")
    for item in evidence.get("specification_results", []):
        suff = item.get("evidence_sufficiency", {})
        threshold = item.get("threshold_boundary_evidence", {})
        print(
            "    - "
            f"{item.get('human_readable')} | obs={item.get('observation_count')} | dates={item.get('represented_trade_date_count')} | "
            f"latest_state={item.get('latest_headline_state')} | transitions={item.get('transition_count')} | "
            f"max_date_share={suff.get('max_date_observation_share')} | min_threshold_distance={threshold.get('minimum_distance_to_threshold')}"
        )


def _print_pair(result: dict) -> None:
    evidence = result.get("relationship_robustness", {})
    default = evidence.get("default_specification", {})
    print("Analytical robustness evidence")
    print(f"  analysis_type: relationship")
    print(f"  pair: {evidence.get('theme_pair')}")
    print(f"  source_mode: {evidence.get('source_mode')}")
    print(f"  default specification: {default.get('human_readable')}")
    print(f"  default specification_id: {default.get('specification_id')}")
    print(f"  evaluated specifications: {evidence.get('evaluated_specification_count', 0)}")
    print(f"  aligned observation count range: {evidence.get('aligned_observation_count_range', {})}")
    print(f"  same-sign observed-share range: {evidence.get('same_sign_observed_share_range', {})}")
    print(f"  exact-state agreement-share range: {evidence.get('exact_state_agreement_share_range', {})}")
    print(f"  same-regime observed-share range: {evidence.get('same_regime_observed_share_range', {})}")
    print(f"  structural-contrast share range: {evidence.get('structural_contrast_share_range', {})}")
    print("  variant table:")
    for item in evidence.get("specification_results", []):
        suff = item.get("evidence_sufficiency", {})
        print(
            "    - "
            f"{item.get('human_readable')} | aligned={item.get('aligned_observation_count')} | dates={item.get('represented_trade_date_count')} | "
            f"same_sign={item.get('same_sign_observed_share')} ({item.get('same_sign_count')}/{item.get('aligned_observation_count')}) | "
            f"same_regime={item.get('same_regime_observed_share')} | structural_contrast={item.get('structural_contrast_share')} | "
            f"max_date_share={suff.get('max_date_observation_share')}"
        )
        if item.get("per_date_results"):
            print(f"      per-date: {item.get('per_date_results')}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.pair and "::" not in args.pair:
        print('Invalid --pair syntax. Expected "THEME_A::THEME_B".', file=sys.stderr)
        return 2
    if not args.pair and not args.theme:
        print("Either --theme or --pair is required.", file=sys.stderr)
        return 2
    policies = SUPPORTED_MATERIALIZATION_POLICIES if args.materialization_policies else (CANONICAL_BUCKET_POLICY,)
    mode = normalize_theme_dynamics_mode(args.mode)
    payload = build_robustness_evidence(
        source_mode=args.source_mode,
        theme=args.theme,
        pair=args.pair,
        calculation_mode=mode,
        bucket_minutes=parse_bucket_minutes(args.bucket_minutes),
        materialization_policies=policies,
        data_dir=args.data_dir,
    )
    if args.all_modes:
        pair_tuple = tuple(part.strip() for part in args.pair.split("::", 1)) if args.pair else None
        payload["calculation_scope_sensitivity"] = compare_calculation_scope_sensitivity(
            theme_name=args.theme,
            pair=pair_tuple,
            source_mode=args.source_mode,
            data_dir=args.data_dir,
        )
    text = json.dumps(_json_safe(payload), ensure_ascii=False, default=str)
    hits = validate_analytical_robustness_text(text)
    if hits:
        print(f"Forbidden robustness wording detected: {hits}", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, default=str))
    else:
        if args.pair:
            _print_pair(payload)
        else:
            _print_theme(payload)
        if args.all_modes:
            print("Calculation-scope sensitivity")
            scope = payload.get("calculation_scope_sensitivity", {})
            print(f"  semantics: {scope.get('semantics')}")
            print(f"  cross-mode state disagreement count: {scope.get('cross_mode_state_disagreement_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
