from __future__ import annotations

import pandas as pd

from src.analytical_continuity import (
    CONTINUITY_SEGMENT_COLUMN,
    RESOLUTION_EXPLICIT_ID_ONLY,
    RESOLUTION_EXPLICIT_VERIFIED,
    RESOLUTION_INFERRED,
    RESOLUTION_SAMPLE_SYNTHETIC,
    RESOLUTION_UNKNOWN,
    attach_continuity_columns,
    build_continuity_segment_id,
    build_continuity_summary,
    resolve_provider_contract_lineage,
    validate_analytical_continuity_text,
)


def test_sample_resolution_is_synthetic_not_primary_provider() -> None:
    lineage = resolve_provider_contract_lineage({"source_mode": "SAMPLE", "data_mode": "SAMPLE"})
    assert lineage["provider_contract_id"] == "sample_synthetic_demo_contract"
    assert lineage["provider_contract_resolution_state"] == RESOLUTION_SAMPLE_SYNTHETIC
    assert lineage[CONTINUITY_SEGMENT_COLUMN]


def test_explicit_verified_and_id_only_are_distinct() -> None:
    verified = resolve_provider_contract_lineage(
        {
            "source_mode": "REAL",
            "provider_contract_id": "contract-a",
            "provider_contract_fingerprint": "fingerprint-a",
        }
    )
    id_only = resolve_provider_contract_lineage(
        {
            "source_mode": "REAL",
            "provider_contract_id": "contract-a",
        }
    )
    assert verified["provider_contract_resolution_state"] == RESOLUTION_EXPLICIT_VERIFIED
    assert id_only["provider_contract_resolution_state"] == RESOLUTION_EXPLICIT_ID_ONLY
    assert verified[CONTINUITY_SEGMENT_COLUMN] != id_only[CONTINUITY_SEGMENT_COLUMN]


def test_inferred_contract_remains_distinguishable_from_explicit() -> None:
    inferred = resolve_provider_contract_lineage(
        {
            "source_mode": "REAL",
            "provider": "AKShare / Eastmoney",
            "api_name": "stock_sector_fund_flow_rank",
            "sector_type": "行业资金流",
            "data_mode": "REAL",
        }
    )
    explicit = resolve_provider_contract_lineage(
        {
            "source_mode": "REAL",
            "provider_contract_id": inferred["provider_contract_id"],
        }
    )
    assert inferred["provider_contract_resolution_state"] == RESOLUTION_INFERRED
    assert explicit["provider_contract_resolution_state"] == RESOLUTION_EXPLICIT_ID_ONLY
    assert inferred[CONTINUITY_SEGMENT_COLUMN] != explicit[CONTINUITY_SEGMENT_COLUMN]


def test_unknown_contract_is_not_upgraded() -> None:
    lineage = resolve_provider_contract_lineage({"source_mode": "REAL", "provider": "other", "api_name": "unknown"})
    assert lineage["provider_contract_id"] == "unknown_provider_contract"
    assert lineage["provider_contract_resolution_state"] == RESOLUTION_UNKNOWN


def test_unknown_contract_marker_is_not_explicit_id() -> None:
    lineage = resolve_provider_contract_lineage(
        {"source_mode": "REAL", "provider_contract_id": "unknown_provider_contract"}
    )
    assert lineage["provider_contract_id"] == "unknown_provider_contract"
    assert lineage["provider_contract_resolution_state"] == RESOLUTION_UNKNOWN


def test_attach_continuity_columns_and_summary() -> None:
    df = pd.DataFrame(
        [
            {"source_mode": "REAL", "provider_contract_id": "contract-a"},
            {"source_mode": "REAL", "provider_contract_id": "contract-a"},
            {"source_mode": "REAL", "provider_contract_id": "contract-b"},
        ]
    )
    attached = attach_continuity_columns(df)
    assert CONTINUITY_SEGMENT_COLUMN in attached.columns
    summary = build_continuity_summary(attached)
    assert summary["continuity_segment_count"] == 2
    assert summary["provider_contract_count"] == 2
    assert summary["dominant_continuity_segment_share"] == 0.6667


def test_segment_id_is_deterministic() -> None:
    assert build_continuity_segment_id("REAL", "a", "explicit_id_only") == build_continuity_segment_id("REAL", "a", "explicit_id_only")
    assert build_continuity_segment_id("REAL", "a", "explicit_id_only") != build_continuity_segment_id("REAL", "a", "inferred_from_provider_metadata")


def test_validate_analytical_continuity_text() -> None:
    assert validate_analytical_continuity_text("这里写了未来会涨和confidence score")
    assert validate_analytical_continuity_text("provider contract continuity segment boundary") == []
