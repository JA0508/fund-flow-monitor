from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analytical_eligibility import (  # noqa: E402
    WORKLOAD_REGIME,
    WORKLOAD_RELATIONSHIP,
    WORKLOAD_ROBUSTNESS,
    WORKLOAD_THEME_CONTINUITY,
    build_availability_vs_qualified_readiness,
    build_qualified_universe_summary,
    filter_eligible_observations,
    validate_analytical_eligibility_text,
)
from src.history_evidence import (  # noqa: E402
    build_historical_coverage_summary,
    build_snapshot_manifest,
    classify_historical_evidence_readiness,
)
from src.sample_data import SAMPLE_DIR  # noqa: E402
from src.theme_dynamics import (  # noqa: E402
    CANONICAL_BUCKET_POLICY,
    build_theme_observation_events,
    materialize_canonical_observations,
)
from src.theme_regimes import attach_regime_signatures_to_observations, build_regime_episodes  # noqa: E402
from src.theme_relationships import build_theme_relationships_from_cube  # noqa: E402


def _default_data_dir(source_mode: str) -> str:
    return SAMPLE_DIR if str(source_mode or "").upper() == "SAMPLE" else "data/ticks"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit workload-specific analytical eligibility without network or writes.")
    parser.add_argument("--source-mode", "--source", choices=["SAMPLE", "REAL"], default="SAMPLE")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--mode", default="strict_representative")
    parser.add_argument("--json", action="store_true")
    return parser


def _counts(df: pd.DataFrame | None, column: str) -> dict[str, int]:
    if df is None or df.empty or column not in df.columns:
        return {}
    return {str(k): int(v) for k, v in df[column].fillna("unknown").astype(str).value_counts().to_dict().items()}


def build_analytical_eligibility_report(
    source_mode: str = "SAMPLE",
    data_dir: str | None = None,
    mode: str = "strict_representative",
) -> dict:
    source = str(source_mode or "SAMPLE").upper()
    directory = data_dir or _default_data_dir(source)
    manifest = build_snapshot_manifest(data_dir=directory, source_mode=source)
    history_summary = build_historical_coverage_summary(manifest)
    history_readiness = classify_historical_evidence_readiness(history_summary)
    events = build_theme_observation_events(source_mode=source, data_dir=directory)
    canonical = materialize_canonical_observations(events, policy=CANONICAL_BUCKET_POLICY)
    continuity_summary = getattr(canonical, "attrs", {}).get("continuity_summary", {})
    theme_summary = build_qualified_universe_summary(canonical, workload=WORKLOAD_THEME_CONTINUITY)
    availability_vs_qualified = build_availability_vs_qualified_readiness(
        history_readiness,
        canonical,
        workload=WORKLOAD_THEME_CONTINUITY,
    )

    regime = attach_regime_signatures_to_observations(canonical, calculation_mode=mode)
    regime_summary = build_qualified_universe_summary(regime, workload=WORKLOAD_REGIME)
    regime_episodes = build_regime_episodes(regime)
    qualified_regime = filter_eligible_observations(regime, workload=WORKLOAD_REGIME)
    qualified_regime_episodes = build_regime_episodes(qualified_regime)

    relationship_bundle = build_theme_relationships_from_cube(canonical, calculation_mode=mode, source_mode=source)
    pair_df = relationship_bundle.get("pair_observations")
    relationship_summary = getattr(pair_df, "attrs", {}).get("analytical_eligibility_summary", {}) if pair_df is not None else {}
    if not relationship_summary:
        relationship_summary = build_qualified_universe_summary(regime, workload=WORKLOAD_RELATIONSHIP)

    robustness_summary = build_qualified_universe_summary(canonical, workload=WORKLOAD_ROBUSTNESS)
    return {
        "source_mode": source,
        "data_dir": directory,
        "network_used": False,
        "historical_availability": {
            "readiness_state": history_readiness.get("readiness_state"),
            "readiness_label": history_readiness.get("readiness_label"),
            "history_span_state": history_summary.get("history_span_state"),
            "intraday_depth_state": history_summary.get("intraday_depth_state"),
            "coverage_consistency_state": history_summary.get("coverage_consistency_state"),
            "valid_snapshot_count": history_summary.get("valid_snapshot_count", 0),
            "trade_date_count": history_summary.get("trade_date_count", 0),
        },
        "availability_vs_qualified": availability_vs_qualified,
        "raw_event_count": int(len(events)),
        "canonical_observation_count": int(len(canonical)),
        "provider_contract_resolution_counts": _counts(canonical, "provider_contract_resolution_state"),
        "continuity_summary": continuity_summary,
        "theme_continuity_eligibility": theme_summary,
        "regime_eligibility": regime_summary,
        "relationship_eligibility": relationship_summary,
        "robustness_eligibility": robustness_summary,
        "regime_observation_count": int(len(regime)),
        "regime_episode_count_all_readable": int(len(regime_episodes)),
        "regime_episode_count_qualified": int(len(qualified_regime_episodes)),
        "relationship_alignment_summary": relationship_bundle.get("alignment_summary", {}),
        "warnings": list(dict.fromkeys(
            [str(item) for item in getattr(events, "attrs", {}).get("warnings", [])]
            + [str(item) for item in getattr(canonical, "attrs", {}).get("warnings", [])]
            + [str(item) for item in relationship_bundle.get("warnings", [])]
        )),
        "errors": [],
    }


def _print_report(report: dict) -> None:
    availability = report.get("historical_availability", {})
    qualified = (report.get("availability_vs_qualified") or {}).get("qualified_summary", {})
    print("Analytical eligibility audit")
    print(f"  source_mode: {report.get('source_mode')}")
    print(f"  data_dir: {report.get('data_dir')}")
    print(f"  network_used: {report.get('network_used')}")
    print(f"  historical availability: {availability.get('readiness_state')} / {availability.get('readiness_label')}")
    print(f"  qualified readiness: {qualified.get('qualified_readiness_state')} / {qualified.get('qualified_readiness_label')}")
    print(f"  canonical observations: {report.get('canonical_observation_count', 0)}")
    print(f"  eligible observations: {qualified.get('eligible_observation_count', 0)}")
    print(f"  excluded observations: {qualified.get('excluded_observation_count', 0)}")
    print(f"  provider contract resolution counts: {report.get('provider_contract_resolution_counts', {})}")
    print(f"  eligible continuity segments: {qualified.get('eligible_continuity_segments', [])}")
    print(f"  qualified trade dates: {qualified.get('eligible_trade_dates', [])}")
    print(f"  exclusion reasons: {qualified.get('excluded_reason_counts', {})}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_analytical_eligibility_report(
        source_mode=args.source_mode,
        data_dir=args.data_dir,
        mode=args.mode,
    )
    text = json.dumps(report, ensure_ascii=False, default=str)
    hits = validate_analytical_eligibility_text(text)
    if hits:
        print(f"Forbidden analytical eligibility wording detected: {hits}", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        _print_report(report)
    return 0 if not report.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
