from __future__ import annotations

import pandas as pd

from src.theme_regimes import (
    attach_regime_signatures_to_observations,
    build_headline_preserving_structural_transitions,
    build_regime_episodes,
    build_regime_signature_record,
    build_regime_transition_trace,
    build_state_equivalent_structural_analysis,
    build_theme_regime_evidence,
    compare_state_equivalent_observations,
    get_regime_observation_basis,
    get_regime_signature_dimensions,
    render_theme_regime_brief_section,
    validate_theme_regime_text,
)


def _row(
    idx: int,
    state: str,
    mode: str = "strict_representative",
    trade_date: str = "2026-01-01",
    bucket: str | None = None,
    member_state: str = "aligned_positive",
    theme_def: str = "def",
    taxonomy: str = "tax",
    source: str = "SAMPLE",
    continuity: str = "segment-a",
    provider_contract_id: str = "sample_synthetic_demo_contract",
    provider_contract_resolution_state: str = "sample_synthetic",
) -> dict:
    bucket = bucket or f"09:{30 + idx:02d}"
    return {
        "canonical_observation_id": f"obs-{idx}-{mode}",
        "observation_id": f"obs-{idx}-{mode}",
        "selected_event_observation_id": f"event-{idx}-{mode}",
        "selected_snapshot_id": f"snapshot-{idx}",
        "theme_name": "半导体/芯片链",
        "trade_date": trade_date,
        "captured_time_bucket": bucket,
        "selected_captured_at": f"{trade_date}T{bucket}:00",
        "selected_captured_time": f"{bucket}:00",
        "source_mode": source,
        "analytical_continuity_segment_id": continuity,
        "provider_contract_id": provider_contract_id,
        "provider_contract_resolution_state": provider_contract_resolution_state,
        "calculation_mode": mode,
        "taxonomy_fingerprint": taxonomy,
        "theme_definition_fingerprint": theme_def,
        "derived_state": state,
        "state_code": {"强流入": 2, "弱流入": 1, "分歧/中性": 0, "弱流出": -1, "强流出": -2}[state],
        "aggregate_value": 10.0,
        "member_structural_state": member_state,
        "member_structure": {"structural_state": member_state, "included_member_count": 3},
    }


def _cube() -> pd.DataFrame:
    rows = []
    states = [
        ("弱流入", "aligned_positive"),
        ("弱流入", "balanced_divergence"),
        ("强流出", "mostly_negative"),
        ("强流出", "mostly_negative"),
        ("弱流入", "balanced_divergence"),
    ]
    for idx, (state, member_state) in enumerate(states):
        rows.append(_row(idx, state, "strict_representative", member_state=member_state))
        rows.append(_row(idx, state, "representative", member_state=member_state))
        breadth_state = "强流出" if idx == 1 else state
        rows.append(_row(idx, breadth_state, "breadth", member_state=member_state))
    return pd.DataFrame(rows)


def test_signature_dimensions_and_basis() -> None:
    assert get_regime_signature_dimensions() == (
        "headline_state",
        "scope_divergence_state",
        "member_divergence_state",
    )
    assert get_regime_observation_basis() == "canonical_bucket_observations"


def test_build_regime_signature_record_is_deterministic_and_human_readable() -> None:
    record = build_regime_signature_record(
        _row(1, "弱流入"),
        scope_divergence_state="representative_positive_breadth_negative",
        member_divergence_state="mixed",
    )
    again = build_regime_signature_record(
        _row(1, "弱流入"),
        scope_divergence_state="representative_positive_breadth_negative",
        member_divergence_state="mixed",
    )
    assert record["regime_signature"] == "弱流入|representative_positive_breadth_negative|mixed"
    assert record["regime_signature_id"] == again["regime_signature_id"]
    assert "score" not in record
    assert record["headline_state_code"] == 1


def test_signature_preserves_insufficient_components() -> None:
    record = build_regime_signature_record(_row(1, "弱流入"), scope_divergence_state="insufficient_scopes", member_divergence_state="insufficient_members")
    assert "insufficient_scopes" in record["regime_signature"]
    assert "insufficient_members" in record["regime_signature"]


def test_attach_regime_signatures_reuses_canonical_scope_and_member_logic() -> None:
    regimes = attach_regime_signatures_to_observations(_cube(), calculation_mode="strict_representative")
    assert not regimes.empty
    assert "scope_divergence_state" in regimes.columns
    assert "member_divergence_state" in regimes.columns
    collided_scope = regimes[regimes["captured_time_bucket"].eq("09:31")].iloc[0]
    assert collided_scope["scope_divergence_state"] == "representative_positive_breadth_negative"
    assert collided_scope["member_divergence_state"] == "balanced_divergence"
    assert regimes["calculation_basis"].eq("canonical_bucket_observations").all()


def test_regime_episodes_segment_a_b_a() -> None:
    regimes = attach_regime_signatures_to_observations(_cube(), calculation_mode="strict_representative")
    episodes = build_regime_episodes(regimes)
    assert len(episodes) == 4
    assert episodes.iloc[0]["canonical_observation_count"] == 1
    assert episodes.iloc[1]["previous_regime_signature"] == episodes.iloc[0]["regime_signature"]
    assert episodes.iloc[0]["span_semantics"] == "observed timestamp span, not continuous regime duration"


def test_regime_episodes_split_same_signature_by_continuity_segment() -> None:
    rows = [
        _row(0, "强流入", source="REAL", provider_contract_id="contract-a", provider_contract_resolution_state="explicit_id_only", bucket="09:30"),
        _row(1, "强流入", source="REAL", provider_contract_id="contract-b", provider_contract_resolution_state="explicit_id_only", bucket="09:31"),
    ]
    regimes = attach_regime_signatures_to_observations(pd.DataFrame(rows), calculation_mode="strict_representative")
    episodes = build_regime_episodes(regimes)
    assert len(episodes) == 2
    assert episodes["regime_signature"].nunique() == 1
    assert episodes["analytical_continuity_segment_id"].nunique() == 2


def test_transition_trace_counts_headline_preserving_structural_change() -> None:
    regimes = attach_regime_signatures_to_observations(_cube(), calculation_mode="strict_representative")
    trace = build_regime_transition_trace(regimes)
    assert trace["observation_count"] == 5
    assert trace["regime_transition_count"] == 3
    assert trace["headline_preserving_structural_change_count"] >= 1
    assert trace["headline_state_change_count"] == 2
    assert "probability" not in str(trace).lower()


def test_headline_preserving_transition_table() -> None:
    regimes = attach_regime_signatures_to_observations(_cube(), calculation_mode="strict_representative")
    transitions = build_headline_preserving_structural_transitions(regimes)
    assert not transitions.empty
    row = transitions.iloc[0]
    assert row["transition_type"] == "headline_preserving_structural_transition"
    assert row["scope_structure_changed"] or row["member_structure_changed"]


def test_state_equivalent_analysis_detects_heterogeneous_structure() -> None:
    regimes = attach_regime_signatures_to_observations(_cube(), calculation_mode="strict_representative")
    analysis = build_state_equivalent_structural_analysis(regimes, headline_state="弱流入")
    assert analysis["analysis_available"] is True
    assert analysis["observation_count"] == 3
    assert analysis["structurally_heterogeneous"] is True
    assert analysis["observed_share_denominator"] == "canonical observations within the selected group"
    assert sum(analysis["regime_signature_observed_shares"].values()) > 0.99


def test_state_equivalent_analysis_detects_homogeneous_structure() -> None:
    regimes = attach_regime_signatures_to_observations(_cube(), calculation_mode="strict_representative")
    analysis = build_state_equivalent_structural_analysis(regimes, headline_state="强流出")
    assert analysis["structurally_homogeneous"] is True
    assert analysis["distinct_regime_signature_count"] == 1


def test_compare_state_equivalent_observations_statuses() -> None:
    regimes = attach_regime_signatures_to_observations(_cube(), calculation_mode="strict_representative")
    weak = regimes[regimes["headline_state"].eq("弱流入")].reset_index(drop=True)
    comparison = compare_state_equivalent_observations(weak.iloc[0], weak.iloc[1])
    assert comparison["same_headline_state"] is True
    assert comparison["same_regime_signature"] is False
    assert comparison["comparison_available"] is True
    different = compare_state_equivalent_observations(regimes.iloc[0], regimes[regimes["headline_state"].eq("强流出")].iloc[0])
    assert different["comparison_status"] == "headline_state_mismatch"
    assert different["comparison_available"] is False


def test_lineage_warnings_for_mixed_source_or_theme_definition() -> None:
    regimes = attach_regime_signatures_to_observations(_cube(), calculation_mode="strict_representative")
    regimes.loc[regimes.index[-1], "source_mode"] = "REAL"
    regimes.loc[regimes.index[-1], "theme_definition_fingerprint"] = "different"
    trace = build_regime_transition_trace(regimes)
    assert any("source mode" in item for item in trace["warnings"])
    assert any("theme-definition" in item for item in trace["warnings"])


def test_build_theme_regime_evidence_sample_path() -> None:
    evidence = build_theme_regime_evidence("半导体/芯片链", source_mode="SAMPLE")
    assert evidence["regime_available"] is True
    assert evidence["source_mode"] == "SAMPLE"
    assert evidence["canonical_observation_basis"] == "canonical_bucket_observations"
    assert any("SAMPLE" in item for item in evidence["warnings"])


def test_render_theme_regime_brief_section_safe() -> None:
    evidence = build_theme_regime_evidence("半导体/芯片链", source_mode="SAMPLE")
    section = render_theme_regime_brief_section(evidence)
    assert "结构状态签名证据" in section
    assert "SAMPLE" in section
    assert validate_theme_regime_text(section) == []


def test_validate_theme_regime_text_catches_forbidden() -> None:
    hits = validate_theme_regime_text("这里写了概率、反转确认和未来会涨")
    assert "概率" in hits
    assert "反转确认" in hits
    assert "未来会涨" in hits
