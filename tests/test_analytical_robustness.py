from __future__ import annotations

import pandas as pd

from src.analytical_robustness import (
    CANONICAL_BUCKET_POLICY,
    build_analytical_specification,
    build_canonical_cube_for_spec,
    build_default_analytical_specification,
    build_evidence_sufficiency_profile,
    build_pair_date_concentration,
    build_robustness_evidence,
    build_threshold_boundary_proximity,
    compare_calculation_scope_sensitivity,
    compare_relationship_specifications,
    compare_theme_specifications,
    parse_bucket_minutes,
    validate_analytical_robustness_text,
)
from src.theme_dynamics import materialize_canonical_observations
from src.theme_relationships import build_relationship_topology_summary


def _taxonomy() -> dict:
    return {
        "themes": [
            {
                "theme_name": "Alpha",
                "theme_group": "G1",
                "members": [{"canonical_name": "A", "enabled": True, "role": "core", "strict_representative": True}],
            },
            {
                "theme_name": "Beta",
                "theme_group": "G1",
                "members": [{"canonical_name": "B", "enabled": True, "role": "core", "strict_representative": True}],
            },
        ]
    }


def _obs(date: str, bucket: str, state: str = "强流入", value: float = 10.0) -> dict:
    return {
        "theme_name": "Alpha",
        "trade_date": date,
        "captured_time_bucket": bucket,
        "calculation_mode": "strict_representative",
        "source_mode": "SAMPLE",
        "taxonomy_fingerprint": "tax",
        "theme_definition_fingerprint": "def",
        "derived_state": state,
        "aggregate_value": value,
    }


def _event(event_id: str, captured_time: str, state: str, value: float, valid: bool = True) -> dict:
    return {
        "event_observation_id": event_id,
        "snapshot_event_id": f"snap-{event_id}",
        "file_snapshot_id": "file-1",
        "theme_name": "Alpha",
        "trade_date": "2026-01-01",
        "captured_time_bucket": "09:30",
        "captured_at": f"2026-01-01 {captured_time}",
        "captured_time": captured_time,
        "calculation_mode": "strict_representative",
        "source_mode": "SAMPLE",
        "taxonomy_fingerprint": "tax",
        "theme_definition_fingerprint": "def",
        "aggregate_value": value,
        "derived_state": state,
        "state_code": 1,
        "contract_ok": valid,
    }


def test_specification_id_is_deterministic_and_semantic():
    spec_a = build_analytical_specification(1, CANONICAL_BUCKET_POLICY, "strict_representative", "SAMPLE", _taxonomy())
    spec_b = build_analytical_specification(1, CANONICAL_BUCKET_POLICY, "strict_representative", "SAMPLE", _taxonomy())
    spec_bucket = build_analytical_specification(5, CANONICAL_BUCKET_POLICY, "strict_representative", "SAMPLE", _taxonomy())
    spec_policy = build_analytical_specification(1, "earliest_valid_snapshot_in_bucket", "strict_representative", "SAMPLE", _taxonomy())
    spec_mode = build_analytical_specification(1, CANONICAL_BUCKET_POLICY, "breadth", "SAMPLE", _taxonomy())
    assert spec_a["specification_id"] == spec_b["specification_id"]
    assert spec_a["specification_id"] != spec_bucket["specification_id"]
    assert spec_a["specification_id"] != spec_policy["specification_id"]
    assert spec_a["specification_id"] != spec_mode["specification_id"]
    assert "bucket=1m" in spec_a["human_readable"]


def test_evidence_sufficiency_profiles_date_distribution():
    empty = build_evidence_sufficiency_profile(pd.DataFrame())
    one = build_evidence_sufficiency_profile(pd.DataFrame([_obs("2026-01-01", "09:30")]))
    concentrated = build_evidence_sufficiency_profile(
        pd.DataFrame([_obs("2026-01-01", f"09:3{i}") for i in range(4)] + [_obs("2026-01-02", "09:30")])
    )
    distributed = build_evidence_sufficiency_profile(
        pd.DataFrame([_obs("2026-01-01", "09:30"), _obs("2026-01-01", "09:31"), _obs("2026-01-02", "09:30"), _obs("2026-01-02", "09:31")])
    )
    assert empty["evidence_sufficiency_state"] == "insufficient_observations"
    assert one["evidence_sufficiency_state"] == "insufficient_observations"
    assert concentrated["evidence_sufficiency_state"] == "multi_date_concentrated"
    assert distributed["evidence_sufficiency_state"] == "multi_date_distributed"
    assert concentrated["max_date_observation_share"] == 0.8
    assert "score" not in concentrated


def test_materialization_policy_audit_variants_preserve_default():
    events = pd.DataFrame(
        [
            _event("e1", "09:30:01", "弱流入", 8.0),
            _event("e2", "09:30:50", "强流入", 31.0),
        ]
    )
    latest = materialize_canonical_observations(events, policy="latest_valid_snapshot_in_bucket")
    earliest = materialize_canonical_observations(events, policy="earliest_valid_snapshot_in_bucket")
    assert latest.iloc[0]["selected_event_observation_id"] == "e2"
    assert earliest.iloc[0]["selected_event_observation_id"] == "e1"
    assert build_default_analytical_specification("SAMPLE")["materialization_policy"] == CANONICAL_BUCKET_POLICY


def test_threshold_boundary_proximity_is_factual():
    df = pd.DataFrame([
        _obs("2026-01-01", "09:30", "弱流入", 5.0),
        _obs("2026-01-02", "09:30", "强流入", 31.0),
    ])
    result = build_threshold_boundary_proximity(df)
    assert result["exact_threshold_hit_count"] == 1
    assert result["minimum_distance_to_threshold"] == 0.0
    assert "thresholds are not changed" in result["distance_semantics"]


def test_parse_bucket_minutes_is_predeclared_ordered_input():
    assert parse_bucket_minutes("1,5,10") == [1, 5, 10]
    assert parse_bucket_minutes("10,5,1,5") == [10, 5, 1]


def test_sample_theme_robustness_has_specification_results():
    result = compare_theme_specifications(
        "半导体/芯片链",
        source_mode="SAMPLE",
        calculation_mode="strict_representative",
        bucket_minutes=(1, 5),
    )
    assert result["evaluated_specification_count"] == 2
    assert result["specification_results"]
    assert "specification_id" in result["specification_results"][0]
    assert result["provider_lineage"]["provider_segment_count"] >= 1
    assert "metadata only" in result["provider_lineage"]["lineage_semantics"]
    assert "robustness_score" not in result


def test_sample_relationship_robustness_exposes_ranges_and_per_date_rows():
    result = compare_relationship_specifications(
        "AI算力/TMT",
        "半导体/芯片链",
        source_mode="SAMPLE",
        calculation_mode="strict_representative",
        bucket_minutes=(1, 5),
    )
    assert result["theme_pair"] == "AI算力/TMT::半导体/芯片链"
    assert result["aligned_observation_count_range"]["max"] >= result["aligned_observation_count_range"]["min"]
    assert result["same_sign_observed_share_range"]["max"] >= result["same_sign_observed_share_range"]["min"]
    assert result["specification_results"][0]["per_date_results"]
    assert "probability" not in str(result).lower()


def test_scope_sensitivity_is_not_ranked():
    result = compare_calculation_scope_sensitivity(theme_name="半导体/芯片链", source_mode="SAMPLE")
    assert len(result["scope_results"]) == 3
    assert "not ranked" in result["semantics"]


def test_pair_date_concentration_per_date_shares():
    pair_df = pd.DataFrame(
        [
            {"trade_date": "2026-01-01", "captured_time_bucket": "09:30", "is_aligned": True, "theme_a_headline_state": "强流入", "theme_b_headline_state": "弱流入"},
            {"trade_date": "2026-01-01", "captured_time_bucket": "09:31", "is_aligned": True, "theme_a_headline_state": "强流入", "theme_b_headline_state": "弱流出"},
            {"trade_date": "2026-01-02", "captured_time_bucket": "09:30", "is_aligned": True, "theme_a_headline_state": "强流出", "theme_b_headline_state": "弱流出"},
        ]
    )
    result = build_pair_date_concentration(pair_df)
    assert result["represented_trade_date_count"] == 2
    assert result["max_date_observation_share"] == 0.6667
    assert len(result["per_date_results"]) == 2


def test_ranking_guardrails_preserve_raw_rows_but_gate_display():
    rows = []
    for idx in range(2):
        rows.append(
            {
                "theme_a": "A",
                "theme_b": "B",
                "theme_pair": "A::B",
                "pair_id": "ab",
                "trade_date": "2026-01-01",
                "captured_time_bucket": f"09:3{idx}",
                "calculation_mode": "strict_representative",
                "source_mode": "SAMPLE",
                "taxonomy_fingerprint": "tax",
                "is_aligned": True,
                "theme_a_headline_state": "强流入",
                "theme_b_headline_state": "弱流入",
                "theme_a_regime_signature": "a",
                "theme_b_regime_signature": "b",
                "theme_a_scope_divergence_state": "x",
                "theme_b_scope_divergence_state": "y",
                "theme_a_member_divergence_state": "x",
                "theme_b_member_divergence_state": "y",
            }
        )
    topology = build_relationship_topology_summary(pd.DataFrame(rows), taxonomy=_taxonomy(), min_aligned_observations=3, min_represented_trade_dates=2)
    assert len(topology) == 1
    assert not bool(topology.iloc[0]["display_eligible"])
    assert "below_min_aligned_observations" in topology.iloc[0]["exclusion_reasons"]
    assert topology.attrs["display_sufficiency"]["excluded_pair_count"] == 1


def test_robustness_evidence_wrapper_and_forbidden_validator():
    evidence = build_robustness_evidence(source_mode="SAMPLE", theme="半导体/芯片链", bucket_minutes=(1,))
    assert evidence["analysis_type"] == "theme"
    assert validate_analytical_robustness_text("建议买 未来会涨 confidence score")
    assert validate_analytical_robustness_text(str(evidence)) == []
