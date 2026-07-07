from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.theme_relationships import (  # noqa: E402
    build_theme_relationship_evidence,
    build_theme_relationships_from_source,
    validate_theme_relationship_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect read-only cross-theme relationship evidence.")
    parser.add_argument("--source-mode", choices=["SAMPLE", "REAL"], default="SAMPLE")
    parser.add_argument("--mode", default="strict_representative")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--theme", default=None, help="Filter topology rows to pairs containing this theme.")
    parser.add_argument("--pair", default=None, help='Inspect one pair as "THEME_A::THEME_B".')
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--top-semantic-overlap", action="store_true")
    parser.add_argument("--top-state-alignment", action="store_true")
    parser.add_argument("--top-structural-contrast", action="store_true")
    parser.add_argument("--co-transitions", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    return parser


def _records_for_json(value):
    if hasattr(value, "to_dict"):
        return value.to_dict(orient="records")
    return value


def _compact_evidence(evidence: dict) -> dict:
    return {
        key: value
        for key, value in evidence.items()
        if key
        not in {
            "pair_observations",
        }
    }


def _print_pair(evidence: dict, co_transitions: bool = False) -> None:
    print("Cross-theme relationship evidence")
    print(f"  pair: {evidence.get('theme_pair')}")
    print(f"  source_mode: {evidence.get('source_mode')}")
    print(f"  mode: {evidence.get('calculation_mode')}")
    print(f"  canonical basis: {evidence.get('canonical_materialization_basis')}")
    print(f"  materialization policy: {evidence.get('materialization_policy')}")
    print(f"  aligned canonical observations: {evidence.get('aligned_observation_count', 0)}")
    print(f"  alignment gaps: {evidence.get('alignment_gap_count', 0)}")
    semantic = evidence.get("semantic_overlap", {})
    headline = evidence.get("headline_state_evidence", {})
    structural = evidence.get("structural_regime_evidence", {})
    transitions = evidence.get("co_transition_evidence", {})
    print("Semantic overlap")
    print(f"  taxonomy_jaccard: {semantic.get('jaccard_overlap', 0.0)}")
    print(f"  shared_member_count: {semantic.get('shared_member_count', 0)}")
    print(f"  shared_strict_count: {semantic.get('shared_strict_count', 0)}")
    print("Observed headline-state alignment")
    print(f"  exact agreement observed share: {headline.get('exact_headline_state_agreement_share', 0.0)}")
    print(f"  same-sign observed share: {headline.get('same_sign_share', 0.0)}")
    print(f"  opposing-sign observed share: {headline.get('opposing_sign_share', 0.0)}")
    print("Structural-regime alignment")
    print(f"  same-regime observed share: {structural.get('same_regime_signature_share', 0.0)}")
    print(f"  headline-aligned/regime-different count: {structural.get('headline_aligned_regime_different_count', 0)}")
    print(f"  headline-aligned/regime-different observed share: {structural.get('headline_aligned_regime_different_share', 0.0)}")
    if co_transitions:
        print("Observed co-transition evidence")
        print(f"  aligned transition steps: {transitions.get('aligned_transition_step_count', 0)}")
        print(f"  simultaneous headline changes: {transitions.get('simultaneous_headline_change_count', 0)}")
        print(f"  simultaneous structural changes: {transitions.get('simultaneous_structural_change_count', 0)}")
        print(f"  denominator: {transitions.get('denominator_note')}")
    warnings = evidence.get("warnings") or []
    if warnings:
        print("Warnings")
        for warning in warnings[:5]:
            print(f"  - {warning}")


def _print_topology(df, title: str, limit: int) -> None:
    print(title)
    if df is None or df.empty:
        print("  no relationship rows")
        return
    columns = [
        "theme_pair",
        "aligned_observations",
        "alignment_gaps",
        "taxonomy_jaccard",
        "same_sign_observed_share",
        "exact_state_observed_share",
        "same_regime_observed_share",
        "headline_aligned_regime_different_count",
        "simultaneous_headline_change_count",
        "simultaneous_structural_change_count",
    ]
    available = [column for column in columns if column in df.columns]
    print(df[available].head(max(1, min(limit, 50))).to_string(index=False))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    limit = max(1, min(int(args.limit or 10), 50))

    bundle = build_theme_relationships_from_source(
        source_mode=args.source_mode,
        calculation_mode=args.mode,
        data_dir=args.data_dir,
    )
    pair_df = bundle.get("pair_observations")
    topology = bundle.get("topology_summary")
    if args.theme and topology is not None and not topology.empty:
        topology = topology[topology["theme_a"].astype(str).eq(args.theme) | topology["theme_b"].astype(str).eq(args.theme)].copy()

    if args.pair:
        if "::" not in args.pair:
            print('Invalid pair syntax. Expected "THEME_A::THEME_B".', file=sys.stderr)
            return 2
        left, right = [part.strip() for part in args.pair.split("::", 1)]
        evidence = build_theme_relationship_evidence(pair_df, left, right)
        text = json.dumps(_compact_evidence(evidence), ensure_ascii=False, default=str) if args.json else str(evidence)
        hits = validate_theme_relationship_text(text)
        if hits:
            print(f"Forbidden relationship wording detected: {hits}", file=sys.stderr)
            return 3
        if args.json:
            print(json.dumps(_compact_evidence(evidence), ensure_ascii=False, indent=2, default=str))
        else:
            _print_pair(evidence, co_transitions=args.co_transitions)
        return 0 if evidence.get("relationship_available") else 1

    if args.top_semantic_overlap:
        topology = topology.sort_values(["taxonomy_jaccard", "aligned_observations", "theme_pair"], ascending=[False, False, True]) if topology is not None and not topology.empty else topology
        title = "Top factual rows by taxonomy Jaccard overlap"
    elif args.top_state_alignment:
        topology = topology.sort_values(["same_sign_observed_share", "aligned_observations", "theme_pair"], ascending=[False, False, True]) if topology is not None and not topology.empty else topology
        title = "Top factual rows by observed same-sign share"
    elif args.top_structural_contrast:
        topology = topology.sort_values(["headline_aligned_regime_different_count", "aligned_observations", "theme_pair"], ascending=[False, False, True]) if topology is not None and not topology.empty else topology
        title = "Top factual rows by headline-aligned/regime-different count"
    else:
        title = "Cross-theme relationship topology summary"

    if args.json:
        payload = {
            "source_mode": args.source_mode,
            "calculation_mode": args.mode,
            "relationship_observation_basis": bundle.get("relationship_observation_basis"),
            "materialization_policy": bundle.get("materialization_policy"),
            "alignment_summary": bundle.get("alignment_summary"),
            "topology_summary": _records_for_json(topology.head(limit) if topology is not None and not topology.empty else topology),
            "warnings": bundle.get("warnings", []),
        }
        text = json.dumps(payload, ensure_ascii=False, default=str)
        hits = validate_theme_relationship_text(text)
        if hits:
            print(f"Forbidden relationship wording detected: {hits}", file=sys.stderr)
            return 3
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        _print_topology(topology, title, limit)
        warnings = bundle.get("warnings") or []
        if warnings:
            print("Warnings")
            for warning in warnings[:5]:
                print(f"  - {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

