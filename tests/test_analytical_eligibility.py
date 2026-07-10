from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.analytical_continuity import (
    RESOLUTION_EXPLICIT_ID_ONLY,
    RESOLUTION_EXPLICIT_VERIFIED,
    RESOLUTION_INFERRED,
    RESOLUTION_SAMPLE_SYNTHETIC,
    RESOLUTION_UNKNOWN,
)
from src.analytical_eligibility import (
    REASON_EXPLICIT_ID_ONLY,
    REASON_INFERRED,
    REASON_REAL_PRIMARY_VERIFIED,
    REASON_SAMPLE_DEMO,
    REASON_UNRESOLVED,
    WORKLOAD_REGIME,
    WORKLOAD_RELATIONSHIP,
    WORKLOAD_ROBUSTNESS,
    WORKLOAD_THEME_CONTINUITY,
    attach_analytical_eligibility,
    build_availability_vs_qualified_readiness,
    build_qualified_universe_summary,
    evaluate_observation_eligibility,
    filter_eligible_observations,
    validate_analytical_eligibility_text,
)
from src.history_evidence import build_historical_coverage_summary, build_snapshot_manifest, classify_historical_evidence_readiness
from src.provider_contracts import build_provider_contract_short_id
from src.provider_registry import get_primary_provider_contract
from src.providers.akshare_sector_flow import normalize_provider_dataframe
from src.theme_dynamics import build_theme_observation_events, materialize_canonical_observations
from src.theme_regimes import attach_regime_signatures_to_observations, build_regime_episodes
from src.theme_relationships import build_theme_relationships_from_cube


def _primary_short_id() -> str:
    return build_provider_contract_short_id(get_primary_provider_contract())


def _primary_fingerprint() -> str:
    return get_primary_provider_contract().to_dict()["semantic_contract_id"]


def _row(source: str = "REAL", resolution: str = RESOLUTION_EXPLICIT_VERIFIED, date: str = "2026-01-01") -> dict:
    return {
        "source_mode": source,
        "trade_date": date,
        "captured_time_bucket": "09:30",
        "theme_name": "半导体/芯片链",
        "calculation_mode": "strict_representative",
        "provider_contract_id": _primary_short_id() if resolution != RESOLUTION_UNKNOWN else "unknown_provider_contract",
        "provider_contract_fingerprint": _primary_fingerprint() if resolution == RESOLUTION_EXPLICIT_VERIFIED else "unknown",
        "provider_contract_resolution_state": resolution,
        "analytical_continuity_segment_id": "seg-a",
    }


def _legacy_snapshot(date: str) -> pd.DataFrame:
    names = ["半导体", "电子", "计算机", "通信", "电池", "银行", "医药生物", "证券Ⅱ"]
    return pd.DataFrame(
        {
            "trade_date": [date] * len(names),
            "captured_at": [f"{date} 09:30:00"] * len(names),
            "captured_time": ["09:30:00"] * len(names),
            "sector_type": ["行业资金流"] * len(names),
            "sector_name": names,
            "main_net_inflow_billion": [10.0, 8.0, 5.0, 4.0, -3.0, 2.0, -1.0, 1.0],
            "source": ["AKShare"] * len(names),
            "data_mode": ["REAL"] * len(names),
        }
    )


def _provider_raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "序号": list(range(1, 9)),
            "名称": ["半导体", "电子", "计算机", "通信", "电池", "银行", "医药生物", "证券Ⅱ"],
            "今日涨跌幅": [1.1, 0.8, 0.5, 0.4, -0.3, 0.2, -0.1, 0.1],
            "今日主力净流入-净额": [1_000_000_000, 800_000_000, 500_000_000, 400_000_000, -300_000_000, 200_000_000, -100_000_000, 100_000_000],
            "今日主力净流入-净占比": [1.0] * 8,
        }
    )


def _write_provider_snapshot(directory: Path, date: str) -> None:
    result = normalize_provider_dataframe(
        _provider_raw_frame(),
        sector_type="行业资金流",
        captured_at=datetime.fromisoformat(f"{date}T09:30:00"),
    )
    result.normalized_df.to_csv(directory / f"sector_flow_{date}.csv", index=False)


def test_historical_availability_does_not_imply_qualified_readiness() -> None:
    availability = {"readiness_state": "multi_day_ready", "readiness_label": "多日历史证据可用", "readiness_reason": "3 dates"}
    legacy = pd.DataFrame([_row(resolution=RESOLUTION_UNKNOWN, date=f"2026-01-0{idx}") for idx in (1, 2, 3)])
    report = build_availability_vs_qualified_readiness(availability, legacy, workload=WORKLOAD_THEME_CONTINUITY)
    qualified = report["qualified_summary"]
    assert report["availability_readiness_state"] == "multi_day_ready"
    assert qualified["qualified_readiness_state"] == "no_qualified_history"
    assert qualified["excluded_observation_count"] == 3
    assert qualified["excluded_reason_counts"][REASON_UNRESOLVED] == 3


def test_explicit_verified_primary_snapshot_is_real_analysis_eligible() -> None:
    result = evaluate_observation_eligibility(_row(), workload=WORKLOAD_THEME_CONTINUITY)
    assert result["is_analytically_eligible"] is True
    assert result["analytical_eligibility_reason"] == REASON_REAL_PRIMARY_VERIFIED


def test_explicit_id_only_and_inferred_are_not_promoted() -> None:
    id_only = evaluate_observation_eligibility(_row(resolution=RESOLUTION_EXPLICIT_ID_ONLY), workload=WORKLOAD_REGIME)
    inferred = evaluate_observation_eligibility(_row(resolution=RESOLUTION_INFERRED), workload=WORKLOAD_RELATIONSHIP)
    assert id_only["is_analytically_eligible"] is False
    assert id_only["analytical_eligibility_reason"] == REASON_EXPLICIT_ID_ONLY
    assert inferred["is_analytically_eligible"] is False
    assert inferred["analytical_eligibility_reason"] == REASON_INFERRED


def test_sample_synthetic_is_sample_demo_eligible_but_not_real() -> None:
    sample_row = _row(source="SAMPLE", resolution=RESOLUTION_SAMPLE_SYNTHETIC)
    sample_row["provider_contract_id"] = "sample_synthetic_demo_contract"
    sample_row["provider_contract_fingerprint"] = "unknown"
    result = evaluate_observation_eligibility(sample_row, workload=WORKLOAD_ROBUSTNESS)
    assert result["is_analytically_eligible"] is True
    assert result["analytical_eligibility_reason"] == REASON_SAMPLE_DEMO

    mixed = pd.DataFrame([sample_row, _row(date="2026-01-02")])
    summary = build_qualified_universe_summary(mixed[mixed["source_mode"].eq("REAL")], workload=WORKLOAD_ROBUSTNESS)
    assert summary["source_mode_counts"] == {"REAL": 1}


def test_mixed_qualified_and_unresolved_history_preserves_both_universes() -> None:
    rows = [
        _row(resolution=RESOLUTION_UNKNOWN, date="2026-01-01"),
        _row(resolution=RESOLUTION_EXPLICIT_VERIFIED, date="2026-01-02"),
        _row(resolution=RESOLUTION_EXPLICIT_VERIFIED, date="2026-01-03"),
    ]
    df = pd.DataFrame(rows)
    attached = attach_analytical_eligibility(df, workload=WORKLOAD_THEME_CONTINUITY)
    eligible = filter_eligible_observations(attached, workload=WORKLOAD_THEME_CONTINUITY)
    summary = build_qualified_universe_summary(attached, workload=WORKLOAD_THEME_CONTINUITY)
    assert len(attached) == 3
    assert len(eligible) == 2
    assert summary["eligible_trade_date_count"] == 2
    assert summary["excluded_reason_counts"][REASON_UNRESOLVED] == 1


def test_regime_and_relationship_denominators_exclude_unresolved_real() -> None:
    cube = pd.DataFrame(
        [
            {**_row(resolution=RESOLUTION_UNKNOWN, date="2026-01-01"), "theme_name": "Alpha", "derived_state": "强流入", "state_code": 2, "taxonomy_fingerprint": "tax", "theme_definition_fingerprint": "def-a", "member_structural_state": "aligned_positive"},
            {**_row(resolution=RESOLUTION_UNKNOWN, date="2026-01-01"), "theme_name": "Beta", "derived_state": "强流入", "state_code": 2, "taxonomy_fingerprint": "tax", "theme_definition_fingerprint": "def-b", "member_structural_state": "aligned_positive"},
        ]
    )
    regimes = attach_regime_signatures_to_observations(cube, calculation_mode="strict_representative")
    qualified_regimes = filter_eligible_observations(regimes, workload=WORKLOAD_REGIME)
    assert build_regime_episodes(qualified_regimes).empty

    bundle = build_theme_relationships_from_cube(cube, source_mode="REAL", taxonomy={"themes": [{"theme_name": "Alpha"}, {"theme_name": "Beta"}]})
    assert bundle["alignment_summary"]["aligned_pair_observation_count"] == 0
    eligibility = bundle["analytical_eligibility_summary"]
    assert eligibility["excluded_observation_count"] == 2


def test_offline_collection_to_qualification_handshake(tmp_path: Path) -> None:
    _write_provider_snapshot(tmp_path, "2026-01-01")
    manifest = build_snapshot_manifest(tmp_path, source_mode="REAL")
    summary = build_historical_coverage_summary(manifest)
    readiness = classify_historical_evidence_readiness(summary)
    events = build_theme_observation_events(source_mode="REAL", data_dir=str(tmp_path))
    canonical = materialize_canonical_observations(events)
    eligibility = build_qualified_universe_summary(canonical, workload=WORKLOAD_THEME_CONTINUITY)
    assert readiness["readiness_state"] in {"single_snapshot", "single_day_intraday", "limited_multi_day"}
    assert not canonical.empty
    assert set(canonical["provider_contract_resolution_state"]) == {RESOLUTION_EXPLICIT_VERIFIED}
    assert canonical["provider_contract_id"].eq(_primary_short_id()).all()
    assert canonical["provider_contract_fingerprint"].eq(_primary_fingerprint()).all()
    assert eligibility["eligible_observation_count"] == len(canonical)


def test_legacy_snapshot_readable_but_excluded_from_qualified_real(tmp_path: Path) -> None:
    _legacy_snapshot("2026-01-01").to_csv(tmp_path / "sector_flow_2026-01-01.csv", index=False)
    manifest = build_snapshot_manifest(tmp_path, source_mode="REAL")
    assert len(manifest) == 1
    events = build_theme_observation_events(source_mode="REAL", data_dir=str(tmp_path))
    canonical = materialize_canonical_observations(events)
    summary = build_qualified_universe_summary(canonical, workload=WORKLOAD_THEME_CONTINUITY)
    assert not canonical.empty
    assert set(canonical["provider_contract_resolution_state"]) == {RESOLUTION_UNKNOWN}
    assert summary["eligible_observation_count"] == 0
    assert summary["excluded_reason_counts"][REASON_UNRESOLVED] == len(canonical)


def test_validate_analytical_eligibility_text() -> None:
    assert validate_analytical_eligibility_text("这里写了未来会涨和readiness score")
    assert validate_analytical_eligibility_text("historical availability differs from qualified analytical readiness") == []
