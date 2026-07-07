from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.theme_pool import THEME_MODE_LABELS  # noqa: E402
from src.theme_regimes import (  # noqa: E402
    build_regime_episodes,
    build_regime_transition_trace,
    build_state_equivalent_structural_analysis,
    build_theme_regime_evidence,
    get_regime_observation_basis,
    get_regime_signature_dimensions,
    validate_theme_regime_text,
)
from src.theme_taxonomy import get_theme_names, load_theme_taxonomy  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect read-only structural regime evidence from canonical theme observations.")
    parser.add_argument("--theme", required=True, help="Theme name configured in theme_taxonomy.json.")
    parser.add_argument("--source-mode", default="SAMPLE", choices=["SAMPLE", "REAL"])
    parser.add_argument("--mode", default="strict_representative", choices=list(THEME_MODE_LABELS.keys()))
    parser.add_argument("--data-dir", default=None, help="Optional CSV directory override.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON evidence.")
    parser.add_argument("--episodes", action="store_true", help="Print regime episodes.")
    parser.add_argument("--transitions", action="store_true", help="Print observed structural regime transitions.")
    parser.add_argument("--state-equivalent", action="store_true", help="Print state-equivalent structural analysis.")
    parser.add_argument("--headline-state", default=None, help="Optional headline state for state-equivalent analysis.")
    parser.add_argument("--date", default=None, help="Optional trade_date filter for displayed observations.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum rows to print.")
    return parser


def _json_safe(value):
    if isinstance(value, pd.DataFrame):
        return value.head(100).to_dict(orient="records")
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
    compact = dict(evidence)
    observations = compact.pop("regime_observations", pd.DataFrame())
    episodes = compact.pop("episodes", pd.DataFrame())
    if isinstance(observations, pd.DataFrame) and not observations.empty:
        safe_columns = [
            "canonical_observation_id",
            "selected_event_observation_id",
            "selected_snapshot_id",
            "theme_name",
            "source_mode",
            "trade_date",
            "captured_time_bucket",
            "calculation_mode",
            "headline_state",
            "scope_divergence_state",
            "member_divergence_state",
            "regime_signature",
            "regime_signature_id",
            "taxonomy_fingerprint",
            "theme_definition_fingerprint",
            "materialization_policy",
            "calculation_basis",
        ]
        available = [column for column in safe_columns if column in observations.columns]
        compact["regime_observation_examples"] = _json_safe(observations[available].head(20))
    else:
        compact["regime_observation_examples"] = []
    compact["episode_examples"] = _json_safe(episodes.head(20)) if isinstance(episodes, pd.DataFrame) else []
    return _json_safe(compact)


def inspect_theme_regimes(
    theme: str,
    source_mode: str = "SAMPLE",
    mode: str = "strict_representative",
    data_dir: str | None = None,
) -> dict:
    taxonomy = load_theme_taxonomy()
    known = set(get_theme_names(taxonomy))
    if theme not in known:
        return {
            "regime_available": False,
            "theme_name": theme,
            "source_mode": source_mode,
            "warnings": [f"未知主题：{theme}。可用主题：{', '.join(sorted(known))}"],
        }
    return build_theme_regime_evidence(
        theme_name=theme,
        source_mode=source_mode,
        calculation_mode=mode,
        taxonomy=taxonomy,
        data_dir=data_dir,
    )


def _print_header(evidence: dict) -> None:
    print("Structural regime evidence")
    print(f"  theme: {evidence.get('theme_name')}")
    print(f"  source_mode: {evidence.get('source_mode')}")
    print(f"  mode: {evidence.get('calculation_mode')}")
    print(f"  signature_dimensions: {' | '.join(get_regime_signature_dimensions())}")
    print(f"  canonical_observation_basis: {get_regime_observation_basis()}")
    print(f"  materialization_policy: {evidence.get('materialization_policy')}")
    print(f"  canonical_observations: {evidence.get('canonical_observation_count', 0)}")
    print(f"  regime_signatures: {evidence.get('regime_signature_count', 0)}")
    print(f"  episodes: {evidence.get('episode_count', 0)}")
    print(f"  latest_signature: {evidence.get('latest_regime_signature') or '--'}")
    print(f"  taxonomy_fingerprint: {str(evidence.get('taxonomy_fingerprint') or '')[:16]}")
    print(f"  theme_definition_fingerprint: {str(evidence.get('theme_definition_fingerprint') or '')[:16]}")
    warnings = evidence.get("warnings") or []
    if warnings:
        print("  warnings:")
        for item in warnings[:10]:
            print(f"    - {item}")


def _print_episodes(evidence: dict, limit: int) -> None:
    episodes = evidence.get("episodes")
    print("Regime episodes")
    if not isinstance(episodes, pd.DataFrame) or episodes.empty:
        print("  <empty>")
        return
    for _, row in episodes.head(max(1, int(limit or 20))).iterrows():
        print(
            "  - "
            f"{row.get('start_trade_date')} {row.get('start_captured_at')} -> "
            f"{row.get('end_trade_date')} {row.get('end_captured_at')} | "
            f"obs={row.get('canonical_observation_count')} | {row.get('regime_signature')}"
        )
    print("  span semantics: observed timestamp span, not continuous regime duration.")


def _print_transitions(evidence: dict) -> None:
    trace = evidence.get("transition_trace") or {}
    print("Observed regime transition trace")
    print(f"  observed_transition_count: {trace.get('regime_transition_count', 0)}")
    print(f"  unchanged_signature_step_count: {trace.get('unchanged_signature_step_count', 0)}")
    print(f"  headline_state_change_count: {trace.get('headline_state_change_count', 0)}")
    print(f"  structural_change_count: {trace.get('structural_change_count', 0)}")
    print(f"  headline_preserving_structural_change_count: {trace.get('headline_preserving_structural_change_count', 0)}")
    print(f"  structural_change_with_headline_change_count: {trace.get('structural_change_with_headline_change_count', 0)}")
    print(f"  latest_regime_transition: {trace.get('latest_regime_transition') or '--'}")
    print(f"  transition_pair_counts: {trace.get('transition_pair_counts', {})}")
    examples = trace.get("headline_preserving_structural_transitions") or []
    if examples:
        print("  headline-preserving structural transitions:")
        for item in examples[:8]:
            print(
                "    - "
                f"{item.get('from_trade_date')} {item.get('from_captured_time_bucket')} -> "
                f"{item.get('to_trade_date')} {item.get('to_captured_time_bucket')} | "
                f"{item.get('headline_state')} | "
                f"{item.get('from_scope_structure')}->{item.get('to_scope_structure')} | "
                f"{item.get('from_member_structure')}->{item.get('to_member_structure')}"
            )
    print("  denominator: observed transition counts use adjacent canonical observations within compatible lineage groups.")


def _print_state_equivalent(evidence: dict, headline_state: str | None) -> None:
    observations = evidence.get("regime_observations")
    if not isinstance(observations, pd.DataFrame):
        observations = pd.DataFrame()
    if headline_state:
        analysis = build_state_equivalent_structural_analysis(observations, headline_state=headline_state)
    else:
        analysis = evidence.get("state_equivalent_analysis") or {}
    print("State-equivalent structural analysis")
    print(f"  headline_state: {analysis.get('headline_state') or '--'}")
    print(f"  canonical_observations: {analysis.get('observation_count', 0)}")
    print(f"  distinct_structural_signatures: {analysis.get('distinct_regime_signature_count', 0)}")
    print(f"  structurally_homogeneous: {analysis.get('structurally_homogeneous')}")
    print(f"  structurally_heterogeneous: {analysis.get('structurally_heterogeneous')}")
    print(f"  signature_counts: {analysis.get('regime_signature_counts', {})}")
    print(f"  observed_signature_shares: {analysis.get('regime_signature_observed_shares', {})}")
    print(f"  scope_structure_counts: {analysis.get('scope_structure_counts', {})}")
    print(f"  member_structure_counts: {analysis.get('member_structure_counts', {})}")
    print(f"  headline_preserving_transition_count: {analysis.get('headline_preserving_structural_transition_count', 0)}")
    print("  denominator: observed structural share = canonical observations within the selected headline-state group; not a future-oriented measure.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evidence = inspect_theme_regimes(
        theme=args.theme,
        source_mode=args.source_mode,
        mode=args.mode,
        data_dir=args.data_dir,
    )
    observations = evidence.get("regime_observations")
    if isinstance(observations, pd.DataFrame) and args.date:
        observations = observations[observations["trade_date"].astype(str).eq(str(args.date))]
        evidence = dict(evidence)
        evidence["regime_observations"] = observations
        evidence["episodes"] = build_regime_episodes(observations)
        evidence["transition_trace"] = build_regime_transition_trace(observations)
        evidence["canonical_observation_count"] = int(len(observations))
        evidence["regime_signature_count"] = int(observations["regime_signature"].nunique()) if not observations.empty else 0
    text_for_check = json.dumps(_compact_evidence(evidence), ensure_ascii=False)
    forbidden = validate_theme_regime_text(text_for_check)
    if args.json:
        print(json.dumps(_compact_evidence(evidence), ensure_ascii=False, indent=2))
    else:
        _print_header(evidence)
        if args.episodes:
            _print_episodes(evidence, args.limit)
        if args.transitions:
            _print_transitions(evidence)
        if args.state_equivalent:
            _print_state_equivalent(evidence, args.headline_state)
    if forbidden:
        print(f"forbidden_hits: {forbidden}", file=sys.stderr)
        return 2
    if not evidence.get("regime_available"):
        return 1 if any("未知主题" in str(item) for item in evidence.get("warnings", [])) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
