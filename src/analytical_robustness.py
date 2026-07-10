from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.analytical_continuity import attach_continuity_columns, build_continuity_summary
from src.analytical_eligibility import (
    WORKLOAD_ROBUSTNESS,
    build_qualified_universe_summary,
    filter_eligible_observations,
)
from src.history_evidence import build_provider_lineage_summary, build_snapshot_manifest
from src.theme_dynamics import (
    CANONICAL_BUCKET_POLICY,
    CAPTURED_TIME_BUCKET_MINUTES,
    DYNAMICS_DEFAULT_BASIS,
    THEME_DYNAMICS_MODES,
    build_state_transition_trace,
    build_theme_observation_events,
    materialize_canonical_observations,
    normalize_theme_dynamics_mode,
)
from src.theme_pool import get_theme_status_thresholds
from src.theme_regimes import attach_regime_signatures_to_observations
from src.theme_relationships import (
    build_headline_state_agreement,
    build_observed_co_transition_evidence,
    build_structural_regime_alignment,
    build_theme_relationship_evidence,
    build_theme_relationships_from_cube,
    normalize_theme_pair,
)
from src.theme_taxonomy import build_taxonomy_fingerprint, load_theme_taxonomy


PREDECLARED_BUCKET_MINUTES = (1, 5, 10)
SUPPORTED_MATERIALIZATION_POLICIES = (
    "latest_valid_snapshot_in_bucket",
    "earliest_valid_snapshot_in_bucket",
)
DEFAULT_MIN_ALIGNED_OBSERVATIONS = 3
DEFAULT_MIN_REPRESENTED_TRADE_DATES = 2
SAMPLE_DATA_DIR = "sample_data/ticks"

INSUFFICIENT_OBSERVATION_COUNT = 3
CONCENTRATED_MAX_DATE_SHARE = 0.75

ROBUSTNESS_FORBIDDEN_WORDS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "抄底",
    "逃顶",
    "推荐买",
    "推荐卖",
    "建议买",
    "建议卖",
    "建仓",
    "清仓",
    "未来会涨",
    "未来会跌",
    "适合配置",
    "应该调仓",
    "趋势确立",
    "反转确认",
    "强烈看好",
    "明确机会",
    "建议关注",
    "confidence score",
    "confidence interval",
    "p-value",
    "statistical significance",
    "probability",
    "win rate",
)


def _stable_id(payload: object, length: int = 16) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _share(numerator: int | float, denominator: int | float) -> float:
    try:
        denom = float(denominator)
        if denom == 0:
            return 0.0
        return round(float(numerator) / denom, 4)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _range(values: Iterable[float | int | None]) -> dict:
    clean = [float(value) for value in values if value is not None and pd.notna(value)]
    if not clean:
        return {"min": None, "max": None}
    return {"min": min(clean), "max": max(clean)}


@dataclass(frozen=True)
class AnalyticalSpecification:
    captured_time_bucket_minutes: int = CAPTURED_TIME_BUCKET_MINUTES
    materialization_policy: str = CANONICAL_BUCKET_POLICY
    calculation_mode: str = "strict_representative"
    source_mode: str = "SAMPLE"
    taxonomy_fingerprint: str = ""
    canonical_observation_basis: str = DYNAMICS_DEFAULT_BASIS
    state_mapping_identity: str = "theme_pool.THEME_STATUS_THRESHOLDS"
    threshold_fingerprint: str = ""


def normalize_bucket_minutes(value: int | str | None) -> int:
    try:
        minutes = int(value or CAPTURED_TIME_BUCKET_MINUTES)
    except (TypeError, ValueError):
        minutes = CAPTURED_TIME_BUCKET_MINUTES
    return max(1, minutes)


def normalize_materialization_policy(policy: str | None) -> str:
    value = str(policy or CANONICAL_BUCKET_POLICY).strip()
    if value in SUPPORTED_MATERIALIZATION_POLICIES:
        return value
    return CANONICAL_BUCKET_POLICY


def build_threshold_fingerprint(thresholds: list[dict] | None = None) -> str:
    return _stable_id(thresholds or get_theme_status_thresholds())


def build_analytical_specification(
    captured_time_bucket_minutes: int = CAPTURED_TIME_BUCKET_MINUTES,
    materialization_policy: str = CANONICAL_BUCKET_POLICY,
    calculation_mode: str = "strict_representative",
    source_mode: str = "SAMPLE",
    taxonomy: dict | None = None,
    taxonomy_fingerprint: str | None = None,
) -> dict:
    taxonomy = taxonomy or load_theme_taxonomy()
    spec = AnalyticalSpecification(
        captured_time_bucket_minutes=normalize_bucket_minutes(captured_time_bucket_minutes),
        materialization_policy=normalize_materialization_policy(materialization_policy),
        calculation_mode=normalize_theme_dynamics_mode(calculation_mode),
        source_mode=str(source_mode or "SAMPLE").upper(),
        taxonomy_fingerprint=taxonomy_fingerprint or build_taxonomy_fingerprint(taxonomy),
        threshold_fingerprint=build_threshold_fingerprint(),
    )
    payload = asdict(spec)
    payload["specification_id"] = _stable_id(payload)
    payload["human_readable"] = (
        f"bucket={payload['captured_time_bucket_minutes']}m|"
        f"policy={payload['materialization_policy']}|"
        f"mode={payload['calculation_mode']}|"
        f"source={payload['source_mode']}|"
        f"taxonomy={payload['taxonomy_fingerprint'][:12]}"
    )
    return payload


def build_default_analytical_specification(
    source_mode: str = "SAMPLE",
    calculation_mode: str = "strict_representative",
    taxonomy: dict | None = None,
) -> dict:
    return build_analytical_specification(
        captured_time_bucket_minutes=CAPTURED_TIME_BUCKET_MINUTES,
        materialization_policy=CANONICAL_BUCKET_POLICY,
        calculation_mode=calculation_mode,
        source_mode=source_mode,
        taxonomy=taxonomy,
    )


def parse_bucket_minutes(value: str | Iterable[int] | None) -> list[int]:
    if value is None:
        return list(PREDECLARED_BUCKET_MINUTES)
    if isinstance(value, str):
        parts = [item.strip() for item in value.split(",")]
    else:
        parts = [str(item) for item in value]
    parsed = [normalize_bucket_minutes(item) for item in parts if str(item).strip()]
    return list(dict.fromkeys(parsed)) or list(PREDECLARED_BUCKET_MINUTES)


def build_canonical_cube_for_spec(
    specification: dict,
    taxonomy: dict | None = None,
    data_dir: str | None = None,
    limit_dates: int | None = None,
) -> pd.DataFrame:
    taxonomy = taxonomy or load_theme_taxonomy()
    events = build_theme_observation_events(
        taxonomy=taxonomy,
        source_mode=specification.get("source_mode", "SAMPLE"),
        data_dir=data_dir,
        calculation_modes=THEME_DYNAMICS_MODES,
        limit_dates=limit_dates,
        bucket_minutes=normalize_bucket_minutes(specification.get("captured_time_bucket_minutes")),
    )
    events = attach_continuity_columns(events)
    canonical = materialize_canonical_observations(
        events,
        policy=normalize_materialization_policy(specification.get("materialization_policy")),
    )
    canonical.attrs["bucket_minutes"] = normalize_bucket_minutes(specification.get("captured_time_bucket_minutes"))
    canonical.attrs["analytical_specification"] = specification
    canonical.attrs["materialization_policy"] = specification.get("materialization_policy")
    canonical.attrs["continuity_universe"] = build_continuity_summary(events)
    return canonical


def _provider_lineage_metadata(source_mode: str, data_dir: str | None = None, bucket_minutes: int = CAPTURED_TIME_BUCKET_MINUTES) -> dict:
    mode = str(source_mode or "SAMPLE").upper()
    directory = data_dir or (SAMPLE_DATA_DIR if mode == "SAMPLE" else "data/ticks")
    manifest = build_snapshot_manifest(directory, source_mode=mode, bucket_minutes=normalize_bucket_minutes(bucket_minutes))
    summary = build_provider_lineage_summary(manifest)
    return {
        "source_mode": mode,
        "data_dir_label": str(Path(directory)),
        "provider_contract_count": summary.get("provider_contract_count", 0),
        "provider_contract_counts": summary.get("provider_contract_counts", {}),
        "provider_segment_count": summary.get("provider_segment_count", 0),
        "provider_segments": summary.get("provider_segments", []),
        "source_homogeneous": summary.get("source_homogeneous", False),
        "provider_lineage_label": summary.get("provider_lineage_label"),
        "provider_lineage_reason": summary.get("provider_lineage_reason"),
        "lineage_semantics": "metadata only; provider lineage is reported alongside robustness evidence and does not change analytical values.",
    }


def _continuity_universe_metadata(cube_df: pd.DataFrame | None) -> dict:
    if cube_df is None:
        return build_continuity_summary(pd.DataFrame())
    return getattr(cube_df, "attrs", {}).get("continuity_universe") or build_continuity_summary(cube_df)


def build_evidence_sufficiency_profile(
    observations_df: pd.DataFrame,
    observation_count_column: str | None = None,
    aligned_only: bool = False,
) -> dict:
    if observations_df is None or observations_df.empty:
        return {
            "observation_count": 0,
            "canonical_observation_count": 0,
            "aligned_observation_count": 0,
            "represented_trade_date_count": 0,
            "represented_trade_dates": [],
            "observations_by_date": {},
            "max_date_observation_share": 0.0,
            "min_observations_per_date": 0,
            "max_observations_per_date": 0,
            "median_observations_per_date": 0,
            "captured_time_bucket_count": 0,
            "alignment_gap_count": 0,
            "alignment_gap_share": 0.0,
            "history_span_state": "no_observations",
            "intraday_depth_state": "no_observations",
            "coverage_consistency_state": "no_observations",
            "evidence_sufficiency_state": "insufficient_observations",
        }
    df = observations_df.copy()
    total_rows = len(df)
    gap_count = 0
    if "is_aligned" in df.columns:
        aligned_mask = df["is_aligned"].astype(bool)
        gap_count = int((~aligned_mask).sum())
        if aligned_only:
            df = df[aligned_mask].copy()
    count = int(len(df))
    if "trade_date" in df.columns and not df.empty:
        by_date = df.groupby(df["trade_date"].astype(str)).size().astype(int).to_dict()
    else:
        by_date = {}
    date_counts = list(by_date.values())
    max_count = max(date_counts) if date_counts else 0
    min_count = min(date_counts) if date_counts else 0
    median_count = int(statistics.median(date_counts)) if date_counts else 0
    max_share = _share(max_count, count)
    represented_dates = sorted(by_date)
    date_count = len(represented_dates)
    if count < INSUFFICIENT_OBSERVATION_COUNT:
        state = "insufficient_observations"
    elif date_count <= 1:
        state = "single_date_only"
    elif max_share >= CONCENTRATED_MAX_DATE_SHARE:
        state = "multi_date_concentrated"
    elif min_count <= 1:
        state = "multi_date_sparse"
    else:
        state = "multi_date_distributed"
    bucket_count = int(df["captured_time_bucket"].dropna().astype(str).nunique()) if "captured_time_bucket" in df.columns and not df.empty else 0
    return {
        "observation_count": count,
        "canonical_observation_count": count,
        "aligned_observation_count": count if aligned_only or "is_aligned" in observations_df.columns else 0,
        "represented_trade_date_count": date_count,
        "represented_trade_dates": represented_dates,
        "observations_by_date": by_date,
        "most_represented_date": max(by_date, key=by_date.get) if by_date else None,
        "least_represented_date": min(by_date, key=by_date.get) if by_date else None,
        "date_observation_count_range": {"min": min_count, "max": max_count},
        "max_date_observation_share": max_share,
        "min_observations_per_date": int(min_count),
        "max_observations_per_date": int(max_count),
        "median_observations_per_date": int(median_count),
        "captured_time_bucket_count": bucket_count,
        "alignment_gap_count": gap_count,
        "alignment_gap_share": _share(gap_count, total_rows),
        **build_continuity_summary(df),
        "history_span_state": "multi_date" if date_count > 1 else ("single_date" if date_count == 1 else "no_observations"),
        "intraday_depth_state": "multi_bucket" if bucket_count > 1 else ("single_bucket" if bucket_count == 1 else "no_observations"),
        "coverage_consistency_state": state,
        "evidence_sufficiency_state": state,
        "state_rules": {
            "insufficient_observations": f"observation_count < {INSUFFICIENT_OBSERVATION_COUNT}",
            "single_date_only": "represented_trade_date_count <= 1",
            "multi_date_concentrated": f"max_date_observation_share >= {CONCENTRATED_MAX_DATE_SHARE}",
            "multi_date_sparse": "min_observations_per_date <= 1",
            "multi_date_distributed": "multi-date observations with more even date contribution",
        },
    }


def _theme_series(cube_df: pd.DataFrame, theme_name: str, mode: str, source_mode: str) -> pd.DataFrame:
    if cube_df is None or cube_df.empty:
        return pd.DataFrame()
    df = cube_df.copy()
    return (
        df[
            df["theme_name"].astype(str).eq(str(theme_name))
            & df["calculation_mode"].astype(str).eq(normalize_theme_dynamics_mode(mode))
            & df["source_mode"].astype(str).str.upper().eq(str(source_mode).upper())
        ]
        .sort_values(["trade_date", "captured_time_bucket"], na_position="last")
        .reset_index(drop=True)
    )


def build_threshold_boundary_proximity(observations_df: pd.DataFrame, top_n: int = 8) -> dict:
    thresholds = sorted(
        {
            float(item[key])
            for item in get_theme_status_thresholds()
            for key in ("lower_bound", "upper_bound")
            if item.get(key) is not None
        }
    )
    if observations_df is None or observations_df.empty or not thresholds or "aggregate_value" not in observations_df.columns:
        return {
            "threshold_evidence_available": False,
            "thresholds": thresholds,
            "exact_threshold_hit_count": 0,
            "minimum_distance_to_threshold": None,
            "median_distance_to_threshold": None,
            "closest_observations": [],
        }
    rows = []
    for _, row in observations_df.iterrows():
        value = pd.to_numeric(pd.Series([row.get("aggregate_value")]), errors="coerce").iloc[0]
        if pd.isna(value):
            continue
        nearest = min(thresholds, key=lambda threshold: abs(float(value) - threshold))
        rows.append(
            {
                "theme_name": row.get("theme_name"),
                "trade_date": row.get("trade_date"),
                "captured_time_bucket": row.get("captured_time_bucket"),
                "derived_state": row.get("derived_state"),
                "aggregate_value": float(value),
                "nearest_state_threshold": nearest,
                "absolute_distance_to_nearest_threshold": round(abs(float(value) - nearest), 6),
                "exact_threshold_hit": bool(abs(float(value) - nearest) == 0),
            }
        )
    distances = [item["absolute_distance_to_nearest_threshold"] for item in rows]
    rows = sorted(rows, key=lambda item: (item["absolute_distance_to_nearest_threshold"], str(item.get("trade_date")), str(item.get("captured_time_bucket"))))
    return {
        "threshold_evidence_available": bool(rows),
        "thresholds": thresholds,
        "exact_threshold_hit_count": int(sum(1 for item in rows if item["exact_threshold_hit"])),
        "minimum_distance_to_threshold": min(distances) if distances else None,
        "median_distance_to_threshold": statistics.median(distances) if distances else None,
        "closest_observations": rows[: max(1, min(int(top_n or 8), 20))],
        "distance_semantics": "within-theme factual distance from aggregate_value to existing theme state thresholds; thresholds are not changed.",
    }


def summarize_theme_variant(cube_df: pd.DataFrame, theme_name: str, specification: dict) -> dict:
    mode = specification.get("calculation_mode", "strict_representative")
    source = specification.get("source_mode", "SAMPLE")
    eligibility_summary = build_qualified_universe_summary(cube_df, workload=WORKLOAD_ROBUSTNESS)
    qualified_cube = filter_eligible_observations(cube_df, workload=WORKLOAD_ROBUSTNESS)
    series = _theme_series(qualified_cube, theme_name, mode, source)
    trace = build_state_transition_trace(series)
    regime = attach_regime_signatures_to_observations(qualified_cube, calculation_mode=mode)
    regime_series = _theme_series(regime, theme_name, mode, source) if not regime.empty else pd.DataFrame()
    threshold = build_threshold_boundary_proximity(series)
    return {
        "specification_id": specification.get("specification_id"),
        "human_readable": specification.get("human_readable"),
        "bucket_minutes": specification.get("captured_time_bucket_minutes"),
        "materialization_policy": specification.get("materialization_policy"),
        "calculation_mode": mode,
        "source_mode": source,
        "observation_count": int(len(series)),
        "represented_trade_date_count": int(series["trade_date"].dropna().astype(str).nunique()) if not series.empty else 0,
        "latest_headline_state": trace.get("latest_state"),
        "state_path": trace.get("state_path", []),
        "state_path_text": trace.get("state_path_text", ""),
        "state_occupancy_share": trace.get("state_occupancy_share", {}),
        "transition_count": int(trace.get("transition_count", 0) or 0),
        "regime_signature_count": int(regime_series["regime_signature"].dropna().astype(str).nunique()) if not regime_series.empty and "regime_signature" in regime_series.columns else 0,
        "headline_preserving_change_count": int(
            sum(
                1
                for idx in range(1, len(regime_series))
                if str(regime_series.iloc[idx - 1].get("headline_state")) == str(regime_series.iloc[idx].get("headline_state"))
                and str(regime_series.iloc[idx - 1].get("regime_signature")) != str(regime_series.iloc[idx].get("regime_signature"))
            )
        )
        if not regime_series.empty
        else 0,
        "evidence_sufficiency": build_evidence_sufficiency_profile(series),
        "analytical_eligibility_summary": eligibility_summary,
        "continuity_universe": _continuity_universe_metadata(cube_df),
        "threshold_boundary_evidence": threshold,
    }


def compare_theme_specifications(
    theme_name: str,
    source_mode: str = "SAMPLE",
    calculation_mode: str = "strict_representative",
    bucket_minutes: Iterable[int] | None = None,
    materialization_policies: Iterable[str] | None = None,
    taxonomy: dict | None = None,
    data_dir: str | None = None,
) -> dict:
    taxonomy = taxonomy or load_theme_taxonomy()
    buckets = parse_bucket_minutes(bucket_minutes)
    policies = [normalize_materialization_policy(item) for item in (materialization_policies or (CANONICAL_BUCKET_POLICY,))]
    specs = [
        build_analytical_specification(bucket, policy, calculation_mode, source_mode, taxonomy)
        for bucket in buckets
        for policy in dict.fromkeys(policies)
    ]
    results = []
    for spec in specs:
        cube = build_canonical_cube_for_spec(spec, taxonomy=taxonomy, data_dir=data_dir)
        results.append(summarize_theme_variant(cube, theme_name, spec))
    latest_states = [item.get("latest_headline_state") for item in results if item.get("latest_headline_state")]
    paths = {tuple(item.get("state_path", [])) for item in results}
    occupancy_keys = sorted({state for item in results for state in item.get("state_occupancy_share", {})})
    occupancy_ranges = {
        state: _range(item.get("state_occupancy_share", {}).get(state, 0.0) for item in results)
        for state in occupancy_keys
    }
    return {
        "robustness_available": bool(results),
        "theme_name": theme_name,
        "source_mode": str(source_mode).upper(),
        "provider_lineage": _provider_lineage_metadata(source_mode, data_dir=data_dir, bucket_minutes=buckets[0] if buckets else CAPTURED_TIME_BUCKET_MINUTES),
        "continuity_universe": results[0].get("continuity_universe") if results else build_continuity_summary(pd.DataFrame()),
        "continuity_universe_consistent": len({json.dumps(item.get("continuity_universe", {}), sort_keys=True, default=str) for item in results}) <= 1 if results else True,
        "default_specification": build_default_analytical_specification(source_mode, calculation_mode, taxonomy),
        "evaluated_specification_count": len(results),
        "specification_results": results,
        "headline_state_path_variant_count": len(paths),
        "latest_headline_state_values": sorted(set(str(item) for item in latest_states)),
        "latest_headline_state_agreement": len(set(latest_states)) <= 1 if latest_states else False,
        "state_occupancy_share_ranges": occupancy_ranges,
        "regime_signature_count_range": _range(item.get("regime_signature_count") for item in results),
        "episode_count_range": _range(item.get("transition_count") for item in results),
        "headline_preserving_change_count_range": _range(item.get("headline_preserving_change_count") for item in results),
        "specification_disagreement_count": max(0, len(paths) - 1),
        "warnings": ["SAMPLE robustness audit uses synthetic demo data only."] if str(source_mode).upper() == "SAMPLE" else [],
    }


def _pair_observations_for_spec(cube_df: pd.DataFrame, pair: tuple[str, str], specification: dict, taxonomy: dict) -> tuple[dict, pd.DataFrame]:
    bundle = build_theme_relationships_from_cube(
        cube_df,
        calculation_mode=specification.get("calculation_mode", "strict_representative"),
        source_mode=specification.get("source_mode", "SAMPLE"),
        taxonomy=taxonomy,
    )
    evidence = build_theme_relationship_evidence(bundle.get("pair_observations"), pair[0], pair[1], taxonomy=taxonomy)
    pair_df = bundle.get("pair_observations")
    if pair_df is not None and not pair_df.empty:
        pair_df = pair_df[
            pair_df["theme_a"].astype(str).eq(pair[0]) & pair_df["theme_b"].astype(str).eq(pair[1])
        ].copy()
    return evidence, pair_df if pair_df is not None else pd.DataFrame()


def build_pair_date_concentration(pair_observations: pd.DataFrame) -> dict:
    if pair_observations is None or pair_observations.empty or "is_aligned" not in pair_observations.columns:
        aligned = pd.DataFrame()
    else:
        aligned = pair_observations[pair_observations["is_aligned"].astype(bool)].copy()
    profile = build_evidence_sufficiency_profile(pair_observations, aligned_only=True)
    rows = []
    if aligned.empty or "trade_date" not in aligned.columns:
        return {
            **profile,
            "per_date_results": rows,
            "same_sign_share_by_date_range": _range(item["same_sign_share"] for item in rows),
            "exact_state_share_by_date_range": _range(item["exact_state_agreement_share"] for item in rows),
            "date_result_semantics": "pooled result is not averaged from per-date shares; per-date rows are factual slices.",
        }
    for date, group in aligned.groupby(aligned["trade_date"].astype(str), sort=True):
        headline = build_headline_state_agreement(group)
        rows.append(
            {
                "trade_date": date,
                "aligned_observation_count": headline.get("aligned_observation_count", 0),
                "same_sign_count": headline.get("same_sign_count", 0),
                "same_sign_share": headline.get("same_sign_share", 0.0),
                "exact_state_agreement_count": headline.get("exact_headline_state_agreement_count", 0),
                "exact_state_agreement_share": headline.get("exact_headline_state_agreement_share", 0.0),
            }
        )
    return {
        **profile,
        "per_date_results": rows,
        "same_sign_share_by_date_range": _range(item["same_sign_share"] for item in rows),
        "exact_state_share_by_date_range": _range(item["exact_state_agreement_share"] for item in rows),
        "date_result_semantics": "pooled result is not averaged from per-date shares; per-date rows are factual slices.",
    }


def summarize_relationship_variant(cube_df: pd.DataFrame, theme_a: str, theme_b: str, specification: dict, taxonomy: dict) -> dict:
    pair = normalize_theme_pair(theme_a, theme_b)
    eligibility_summary = build_qualified_universe_summary(cube_df, workload=WORKLOAD_ROBUSTNESS)
    evidence, pair_df = _pair_observations_for_spec(cube_df, pair, specification, taxonomy)
    headline = evidence.get("headline_state_evidence", {})
    structural = evidence.get("structural_regime_evidence", {})
    transitions = evidence.get("co_transition_evidence", {})
    date_concentration = build_pair_date_concentration(pair_df)
    return {
        "specification_id": specification.get("specification_id"),
        "human_readable": specification.get("human_readable"),
        "bucket_minutes": specification.get("captured_time_bucket_minutes"),
        "materialization_policy": specification.get("materialization_policy"),
        "calculation_mode": specification.get("calculation_mode"),
        "source_mode": specification.get("source_mode"),
        "aligned_observation_count": int(evidence.get("aligned_observation_count", 0)),
        "represented_trade_date_count": int(evidence.get("represented_trade_date_count", 0)),
        "same_sign_count": int(headline.get("same_sign_count", 0)),
        "same_sign_observed_share": headline.get("same_sign_share", 0.0),
        "exact_state_agreement_count": int(headline.get("exact_headline_state_agreement_count", 0)),
        "exact_state_agreement_share": headline.get("exact_headline_state_agreement_share", 0.0),
        "opposing_sign_count": int(headline.get("opposing_sign_count", 0)),
        "opposing_sign_share": headline.get("opposing_sign_share", 0.0),
        "same_regime_count": int(structural.get("same_regime_signature_count", 0)),
        "same_regime_observed_share": structural.get("same_regime_signature_share", 0.0),
        "structural_contrast_count": int(structural.get("headline_aligned_regime_different_count", 0)),
        "structural_contrast_share": structural.get("headline_aligned_regime_different_share", 0.0),
        "simultaneous_headline_change_count": int(transitions.get("simultaneous_headline_change_count", 0)),
        "simultaneous_structural_change_count": int(transitions.get("simultaneous_structural_change_count", 0)),
        "evidence_sufficiency": date_concentration,
        "analytical_eligibility_summary": evidence.get("analytical_eligibility_summary") or eligibility_summary,
        "continuity_universe": _continuity_universe_metadata(cube_df),
        "per_date_results": date_concentration.get("per_date_results", []),
    }


def compare_relationship_specifications(
    theme_a: str,
    theme_b: str,
    source_mode: str = "SAMPLE",
    calculation_mode: str = "strict_representative",
    bucket_minutes: Iterable[int] | None = None,
    materialization_policies: Iterable[str] | None = None,
    taxonomy: dict | None = None,
    data_dir: str | None = None,
) -> dict:
    taxonomy = taxonomy or load_theme_taxonomy()
    left, right = normalize_theme_pair(theme_a, theme_b)
    buckets = parse_bucket_minutes(bucket_minutes)
    policies = [normalize_materialization_policy(item) for item in (materialization_policies or (CANONICAL_BUCKET_POLICY,))]
    specs = [
        build_analytical_specification(bucket, policy, calculation_mode, source_mode, taxonomy)
        for bucket in buckets
        for policy in dict.fromkeys(policies)
    ]
    results = []
    for spec in specs:
        cube = build_canonical_cube_for_spec(spec, taxonomy=taxonomy, data_dir=data_dir)
        results.append(summarize_relationship_variant(cube, left, right, spec, taxonomy))
    return {
        "robustness_available": bool(results),
        "theme_pair": f"{left}::{right}",
        "source_mode": str(source_mode).upper(),
        "provider_lineage": _provider_lineage_metadata(source_mode, data_dir=data_dir, bucket_minutes=buckets[0] if buckets else CAPTURED_TIME_BUCKET_MINUTES),
        "continuity_universe": results[0].get("continuity_universe") if results else build_continuity_summary(pd.DataFrame()),
        "continuity_universe_consistent": len({json.dumps(item.get("continuity_universe", {}), sort_keys=True, default=str) for item in results}) <= 1 if results else True,
        "default_specification": build_default_analytical_specification(source_mode, calculation_mode, taxonomy),
        "evaluated_specification_count": len(results),
        "specification_results": results,
        "aligned_observation_count_range": _range(item.get("aligned_observation_count") for item in results),
        "represented_trade_date_count_range": _range(item.get("represented_trade_date_count") for item in results),
        "same_sign_observed_share_range": _range(item.get("same_sign_observed_share") for item in results),
        "exact_state_agreement_share_range": _range(item.get("exact_state_agreement_share") for item in results),
        "opposing_sign_share_range": _range(item.get("opposing_sign_share") for item in results),
        "same_regime_observed_share_range": _range(item.get("same_regime_observed_share") for item in results),
        "structural_contrast_share_range": _range(item.get("structural_contrast_share") for item in results),
        "co_transition_count_range": _range(item.get("simultaneous_headline_change_count") for item in results),
        "warnings": ["SAMPLE robustness audit uses synthetic demo data only."] if str(source_mode).upper() == "SAMPLE" else [],
    }


def compare_calculation_scope_sensitivity(
    theme_name: str | None = None,
    pair: tuple[str, str] | None = None,
    source_mode: str = "SAMPLE",
    taxonomy: dict | None = None,
    data_dir: str | None = None,
) -> dict:
    taxonomy = taxonomy or load_theme_taxonomy()
    if pair:
        rows = [
            summarize_relationship_variant(
                build_canonical_cube_for_spec(build_default_analytical_specification(source_mode, mode, taxonomy), taxonomy, data_dir),
                pair[0],
                pair[1],
                build_default_analytical_specification(source_mode, mode, taxonomy),
                taxonomy,
            )
            for mode in THEME_DYNAMICS_MODES
        ]
    else:
        rows = [
            summarize_theme_variant(
                build_canonical_cube_for_spec(build_default_analytical_specification(source_mode, mode, taxonomy), taxonomy, data_dir),
                str(theme_name),
                build_default_analytical_specification(source_mode, mode, taxonomy),
            )
            for mode in THEME_DYNAMICS_MODES
        ]
    states = [row.get("latest_headline_state") for row in rows if row.get("latest_headline_state")]
    return {
        "scope_sensitivity_available": bool(rows),
        "source_mode": str(source_mode).upper(),
        "scope_results": rows,
        "cross_mode_state_disagreement_count": max(0, len(set(states)) - 1) if states else 0,
        "semantics": "calculation modes are semantic scopes; rows are not ranked and no mode is selected from outcomes.",
    }


def build_robustness_evidence(
    source_mode: str = "SAMPLE",
    theme: str | None = None,
    pair: str | tuple[str, str] | None = None,
    calculation_mode: str = "strict_representative",
    bucket_minutes: Iterable[int] | None = None,
    materialization_policies: Iterable[str] | None = None,
    taxonomy: dict | None = None,
    data_dir: str | None = None,
) -> dict:
    taxonomy = taxonomy or load_theme_taxonomy()
    if pair:
        left, right = pair.split("::", 1) if isinstance(pair, str) else pair
        relationship = compare_relationship_specifications(
            left,
            right,
            source_mode=source_mode,
            calculation_mode=calculation_mode,
            bucket_minutes=bucket_minutes,
            materialization_policies=materialization_policies,
            taxonomy=taxonomy,
            data_dir=data_dir,
        )
        return {"analysis_type": "relationship", "relationship_robustness": relationship}
    if not theme:
        return {"analysis_type": "theme", "theme_robustness": {"robustness_available": False, "warnings": ["未指定 theme。"]}}
    theme_result = compare_theme_specifications(
        theme,
        source_mode=source_mode,
        calculation_mode=calculation_mode,
        bucket_minutes=bucket_minutes,
        materialization_policies=materialization_policies,
        taxonomy=taxonomy,
        data_dir=data_dir,
    )
    return {"analysis_type": "theme", "theme_robustness": theme_result}


def summarize_robustness_for_display(evidence: dict) -> dict:
    if not evidence:
        return {"summary_label": "暂无稳健性证据", "summary_reason": "未生成 analytical robustness evidence。"}
    result = evidence.get("relationship_robustness") or evidence.get("theme_robustness") or {}
    label = "分析稳健性证据可用" if result.get("robustness_available") else "暂无稳健性证据"
    reason = (
        "结果以预声明规格的事实区间、观察数量、日期覆盖和分母展示，不形成单一分数。"
        if result.get("robustness_available")
        else "当前样本不足或未指定分析对象。"
    )
    return {"summary_label": label, "summary_reason": reason}


def validate_analytical_robustness_text(text: str) -> list[str]:
    value = str(text or "")
    return [word for word in ROBUSTNESS_FORBIDDEN_WORDS if word in value]
