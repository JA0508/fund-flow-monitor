from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analytical_continuity import (  # noqa: E402
    CONTINUITY_SEGMENT_COLUMN,
    build_continuity_summary,
    validate_analytical_continuity_text,
)
from src.analytical_robustness import build_robustness_evidence  # noqa: E402
from src.theme_dynamics import (  # noqa: E402
    CANONICAL_BUCKET_POLICY,
    analyze_observation_bucket_collisions,
    build_bucket_collision_summary,
    build_theme_observation_events,
    materialize_canonical_observations,
)
from src.theme_regimes import attach_regime_signatures_to_observations, build_regime_episodes  # noqa: E402
from src.theme_relationships import build_theme_relationships_from_cube  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit provider-contract-aware analytical continuity without live fetching.")
    parser.add_argument("--source-mode", "--source", choices=["SAMPLE", "REAL"], default="SAMPLE")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--theme", default="AI算力/TMT")
    parser.add_argument("--pair", default="AI算力/TMT::半导体/芯片链")
    parser.add_argument("--mode", default="strict_representative")
    parser.add_argument("--json", action="store_true")
    return parser


def _records(df: pd.DataFrame | None, limit: int = 5) -> list[dict]:
    if df is None or df.empty:
        return []
    return df.head(max(1, int(limit or 5))).to_dict(orient="records")


def build_analytical_continuity_report(
    source_mode: str = "SAMPLE",
    data_dir: str | None = None,
    theme: str = "AI算力/TMT",
    pair: str = "AI算力/TMT::半导体/芯片链",
    mode: str = "strict_representative",
) -> dict:
    source = str(source_mode or "SAMPLE").upper()
    events = build_theme_observation_events(source_mode=source, data_dir=data_dir)
    canonical = materialize_canonical_observations(events, policy=CANONICAL_BUCKET_POLICY)
    collisions = analyze_observation_bucket_collisions(events)
    collided = collisions[collisions.get("event_count", pd.Series(dtype=int)).fillna(0).astype(int).gt(1)].copy() if not collisions.empty else pd.DataFrame()
    cross_segment_collisions = (
        collided[
            collided["analytical_continuity_segment_ids"].apply(lambda value: isinstance(value, list) and len(set(value)) > 1)
        ].copy()
        if not collided.empty and "analytical_continuity_segment_ids" in collided.columns
        else pd.DataFrame()
    )
    regime = attach_regime_signatures_to_observations(canonical, calculation_mode=mode)
    episodes = build_regime_episodes(regime, theme_name=theme)
    relationship_bundle = build_theme_relationships_from_cube(canonical, calculation_mode=mode, source_mode=source)
    pair_rows = relationship_bundle.get("pair_observations")
    robustness = build_robustness_evidence(source_mode=source, theme=theme, calculation_mode=mode, data_dir=data_dir)
    relationship_robustness = build_robustness_evidence(source_mode=source, pair=pair, calculation_mode=mode, data_dir=data_dir)
    continuity_summary = build_continuity_summary(canonical)
    report = {
        "source_mode": source,
        "network_used": False,
        "continuity_summary": continuity_summary,
        "raw_event_count": int(len(events)),
        "canonical_observation_count": int(len(canonical)),
        "bucket_collision_summary": build_bucket_collision_summary(collisions),
        "cross_segment_collision_count": int(len(cross_segment_collisions)),
        "cross_segment_collision_examples": _records(cross_segment_collisions),
        "canonical_continuity_segments": sorted(canonical[CONTINUITY_SEGMENT_COLUMN].dropna().astype(str).unique().tolist()) if not canonical.empty and CONTINUITY_SEGMENT_COLUMN in canonical.columns else [],
        "regime_episode_count": int(len(episodes)),
        "regime_episode_continuity_segment_count": int(episodes[CONTINUITY_SEGMENT_COLUMN].dropna().astype(str).nunique()) if not episodes.empty and CONTINUITY_SEGMENT_COLUMN in episodes.columns else 0,
        "relationship_alignment_summary": relationship_bundle.get("alignment_summary", {}),
        "relationship_continuity_segment_count": int(pair_rows[CONTINUITY_SEGMENT_COLUMN].dropna().astype(str).nunique()) if pair_rows is not None and not pair_rows.empty and CONTINUITY_SEGMENT_COLUMN in pair_rows.columns else 0,
        "theme_robustness_continuity_universe": (robustness.get("theme_robustness") or {}).get("continuity_universe", {}),
        "theme_robustness_continuity_universe_consistent": (robustness.get("theme_robustness") or {}).get("continuity_universe_consistent"),
        "relationship_robustness_continuity_universe": (relationship_robustness.get("relationship_robustness") or {}).get("continuity_universe", {}),
        "relationship_robustness_continuity_universe_consistent": (relationship_robustness.get("relationship_robustness") or {}).get("continuity_universe_consistent"),
        "legacy_or_unresolved_contract_observation_count": int(continuity_summary.get("unknown_contract_observation_count", 0) or 0)
        + int(continuity_summary.get("inferred_contract_observation_count", 0) or 0),
        "warnings": list(dict.fromkeys(
            [str(item) for item in getattr(events, "attrs", {}).get("warnings", [])]
            + [str(item) for item in getattr(canonical, "attrs", {}).get("warnings", [])]
            + [str(item) for item in relationship_bundle.get("warnings", [])]
        )),
        "errors": [],
    }
    report["continuity_label"] = (
        "analytical continuity segmented"
        if report["continuity_summary"].get("continuity_segment_count", 0) >= 1
        else "no analytical continuity observations"
    )
    return report


def _print_report(report: dict) -> None:
    print("Analytical continuity audit")
    print(f"  source_mode: {report.get('source_mode')}")
    print(f"  network_used: {report.get('network_used')}")
    print(f"  continuity_label: {report.get('continuity_label')}")
    summary = report.get("continuity_summary") or {}
    print(f"  continuity segments: {summary.get('continuity_segment_count', 0)}")
    print(f"  provider contracts: {summary.get('provider_contract_counts', {})}")
    print(f"  resolution states: {summary.get('resolution_state_counts', {})}")
    print(f"  raw events: {report.get('raw_event_count', 0)}")
    print(f"  canonical observations: {report.get('canonical_observation_count', 0)}")
    print(f"  cross-segment bucket collisions: {report.get('cross_segment_collision_count', 0)}")
    print(f"  regime episodes: {report.get('regime_episode_count', 0)}")
    print(f"  relationship continuity segments: {report.get('relationship_continuity_segment_count', 0)}")
    print(f"  theme robustness continuity universe consistent: {report.get('theme_robustness_continuity_universe_consistent')}")
    print(f"  relationship robustness continuity universe consistent: {report.get('relationship_robustness_continuity_universe_consistent')}")
    for warning in report.get("warnings") or []:
        print(f"  warning: {warning}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_analytical_continuity_report(
        source_mode=args.source_mode,
        data_dir=args.data_dir,
        theme=args.theme,
        pair=args.pair,
        mode=args.mode,
    )
    text = json.dumps(report, ensure_ascii=False, default=str)
    hits = validate_analytical_continuity_text(text)
    if hits:
        print(f"Forbidden analytical continuity wording detected: {hits}", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        _print_report(report)
    return 0 if not report.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
