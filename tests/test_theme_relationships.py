from __future__ import annotations

import pandas as pd

from src.theme_relationships import (
    build_aligned_theme_pairs,
    build_headline_state_agreement,
    build_observed_co_transition_evidence,
    build_pair_semantic_overlap_lookup,
    build_structural_regime_alignment,
    build_theme_pair_id,
    build_theme_relationship_evidence,
    build_theme_relationships_from_cube,
    filter_pair_observations,
    get_theme_relationship_pair_grain,
    normalize_theme_pair,
    render_theme_relationship_brief_section,
    validate_theme_relationship_text,
)


def _taxonomy() -> dict:
    return {
        "themes": [
            {
                "theme_name": "Alpha",
                "theme_group": "G1",
                "members": [
                    {"canonical_name": "A1", "enabled": True, "role": "core", "strict_representative": True},
                    {"canonical_name": "Shared", "enabled": True, "role": "satellite", "strict_representative": False},
                ],
            },
            {
                "theme_name": "Beta",
                "theme_group": "G1",
                "members": [
                    {"canonical_name": "B1", "enabled": True, "role": "core", "strict_representative": True},
                    {"canonical_name": "Shared", "enabled": True, "role": "satellite", "strict_representative": False},
                ],
            },
            {
                "theme_name": "Gamma",
                "theme_group": "G2",
                "members": [{"canonical_name": "G1", "enabled": True, "role": "core", "strict_representative": True}],
            },
        ]
    }


def _row(theme: str, date: str, bucket: str, state: str, code: int, signature: str, source: str = "SAMPLE") -> dict:
    return {
        "theme_name": theme,
        "theme_id": theme,
        "trade_date": date,
        "captured_time_bucket": bucket,
        "calculation_mode": "strict_representative",
        "source_mode": source,
        "taxonomy_fingerprint": "tax-1",
        "theme_definition_fingerprint": f"def-{theme}",
        "derived_state": state,
        "state_code": code,
        "state_group": "positive" if code > 0 else "negative" if code < 0 else "neutral",
        "canonical_observation_id": f"obs-{theme}-{date}-{bucket}-{source}",
        "selected_snapshot_id": f"snap-{date}-{bucket}-{source}",
        "selected_event_observation_id": f"evt-{theme}-{date}-{bucket}-{source}",
        "member_structural_state": "mostly_positive" if code > 0 else "mostly_negative" if code < 0 else "balanced_divergence",
    }


def _cube() -> pd.DataFrame:
    rows = [
        _row("Alpha", "2026-01-01", "09:30", "强流入", 2, "unused"),
        _row("Beta", "2026-01-01", "09:30", "弱流入", 1, "unused"),
        _row("Gamma", "2026-01-01", "09:30", "强流出", -2, "unused"),
        _row("Alpha", "2026-01-02", "09:30", "强流入", 2, "unused"),
        _row("Beta", "2026-01-02", "09:30", "强流入", 2, "unused"),
        _row("Gamma", "2026-01-02", "09:30", "弱流出", -1, "unused"),
        _row("Alpha", "2026-01-03", "09:30", "弱流出", -1, "unused"),
        _row("Beta", "2026-01-03", "09:30", "弱流出", -1, "unused"),
        # Gamma is intentionally missing on 2026-01-03 to preserve an alignment gap.
        _row("Alpha", "2026-01-01", "09:30", "强流入", 2, "unused", source="REAL"),
        _row("Beta", "2026-01-01", "09:30", "强流入", 2, "unused", source="REAL"),
    ]
    df = pd.DataFrame(rows)
    df.attrs["materialization_policy"] = "latest_valid_snapshot_in_bucket"
    df.attrs["dynamics_basis"] = "canonical_bucket_observations"
    return df


def test_pair_identity_is_unordered_and_deterministic():
    assert normalize_theme_pair("Beta", "Alpha") == ("Alpha", "Beta")
    assert build_theme_pair_id("Beta", "Alpha", "tax") == build_theme_pair_id("Alpha", "Beta", "tax")
    assert "calculation_mode" in get_theme_relationship_pair_grain()


def test_alignment_uses_exact_canonical_bucket_and_preserves_gaps():
    pairs = build_aligned_theme_pairs(_cube(), calculation_mode="strict_representative", source_mode="SAMPLE", taxonomy=_taxonomy())
    alpha_gamma = filter_pair_observations(pairs, "Alpha", "Gamma")
    assert int(alpha_gamma["is_aligned"].sum()) == 2
    assert int((~alpha_gamma["is_aligned"]).sum()) == 1
    assert set(alpha_gamma["source_mode"]) == {"SAMPLE"}
    assert "missing_theme_b" in set(alpha_gamma["alignment_status"])


def test_real_and_sample_are_not_silently_mixed():
    sample_pairs = build_aligned_theme_pairs(_cube(), source_mode="SAMPLE", taxonomy=_taxonomy())
    real_pairs = build_aligned_theme_pairs(_cube(), source_mode="REAL", taxonomy=_taxonomy())
    assert set(sample_pairs["source_mode"]) == {"SAMPLE"}
    assert set(real_pairs["source_mode"]) == {"REAL"}


def test_headline_agreement_distinguishes_exact_same_sign_and_opposing():
    pairs = build_aligned_theme_pairs(_cube(), source_mode="SAMPLE", taxonomy=_taxonomy())
    alpha_beta = filter_pair_observations(pairs, "Alpha", "Beta")
    evidence = build_headline_state_agreement(alpha_beta)
    assert evidence["aligned_observation_count"] == 3
    assert evidence["exact_headline_state_agreement_count"] == 2
    assert evidence["same_sign_count"] == 3
    assert evidence["opposing_sign_count"] == 0
    assert evidence["denominator_note"].startswith("all aligned canonical")


def test_structural_regime_alignment_finds_headline_aligned_regime_difference():
    pairs = build_aligned_theme_pairs(_cube(), source_mode="SAMPLE", taxonomy=_taxonomy())
    alpha_beta = filter_pair_observations(pairs, "Alpha", "Beta")
    same_headline_idx = alpha_beta[
        alpha_beta["theme_a_headline_state"].astype(str).eq(alpha_beta["theme_b_headline_state"].astype(str))
    ].index[0]
    alpha_beta.loc[same_headline_idx, "theme_b_regime_signature"] = "different-structure"
    structural = build_structural_regime_alignment(alpha_beta)
    assert structural["headline_aligned_regime_different_count"] >= 1
    assert "headline-aligned canonical pair observations" in structural["headline_aligned_regime_different_denominator_note"]


def test_co_transition_counts_are_observed_counts_not_probabilities():
    pairs = build_aligned_theme_pairs(_cube(), source_mode="SAMPLE", taxonomy=_taxonomy())
    alpha_beta = filter_pair_observations(pairs, "Alpha", "Beta")
    transitions = build_observed_co_transition_evidence(alpha_beta)
    assert transitions["aligned_transition_step_count"] == 2
    assert "transition steps" in transitions["denominator_note"]
    assert "probability" not in str(transitions).lower()


def test_semantic_overlap_reuses_taxonomy_audit_fields():
    lookup = build_pair_semantic_overlap_lookup(_taxonomy())
    record = lookup["Alpha::Beta"]
    assert record["shared_member_count"] == 1
    assert record["member_union_count"] == 3
    assert record["jaccard_overlap"] == 0.3333
    assert "overlap_state" in record


def test_full_relationship_evidence_has_no_overall_score():
    pairs = build_aligned_theme_pairs(_cube(), source_mode="SAMPLE", taxonomy=_taxonomy())
    evidence = build_theme_relationship_evidence(pairs, "Beta", "Alpha", taxonomy=_taxonomy())
    assert evidence["theme_pair"] == "Alpha::Beta"
    assert evidence["aligned_observation_count"] == 3
    assert "score" not in evidence
    assert evidence["semantic_overlap"]["shared_member_count"] == 1


def test_relationships_from_cube_builds_topology_summary():
    bundle = build_theme_relationships_from_cube(_cube(), source_mode="SAMPLE", taxonomy=_taxonomy())
    topology = bundle["topology_summary"]
    assert not topology.empty
    assert {"theme_pair", "same_sign_observed_share", "headline_aligned_regime_different_count"}.issubset(topology.columns)


def test_relationship_brief_text_is_safe():
    pairs = build_aligned_theme_pairs(_cube(), source_mode="SAMPLE", taxonomy=_taxonomy())
    evidence = build_theme_relationship_evidence(pairs, "Alpha", "Beta", taxonomy=_taxonomy())
    section = render_theme_relationship_brief_section(evidence)
    assert "主题关系证据" in section
    assert validate_theme_relationship_text(section) == []
    assert validate_theme_relationship_text("建议买 未来会涨 predictive") != []
