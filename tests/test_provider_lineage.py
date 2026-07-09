from __future__ import annotations

import pandas as pd

from src.history_evidence import build_provider_lineage_summary, build_provider_segments


def _manifest(contracts: list[str]) -> pd.DataFrame:
    rows = []
    for idx, contract_id in enumerate(contracts):
        rows.append(
            {
                "file_name": f"sector_flow_2026-01-0{idx + 1}.csv",
                "trade_date": f"2026-01-0{idx + 1}",
                "captured_time": "10:00:00",
                "captured_time_count": 1,
                "provider": "AKShare / Eastmoney",
                "api_name": "stock_sector_fund_flow_rank",
                "provider_contract_id": contract_id,
                "data_mode": "REAL",
                "is_readable": True,
                "is_empty": False,
            }
        )
    return pd.DataFrame(rows)


def test_one_provider_one_segment_homogeneous():
    summary = build_provider_lineage_summary(_manifest(["a", "a", "a"]))
    assert summary["provider_contract_count"] == 1
    assert summary["provider_segment_count"] == 1
    assert summary["source_homogeneous"] is True


def test_provider_change_creates_new_segment():
    segments = build_provider_segments(_manifest(["a", "b", "b"]))
    assert [row["provider_contract_id"] for row in segments] == ["a", "b"]


def test_provider_aba_creates_three_segments():
    summary = build_provider_lineage_summary(_manifest(["a", "b", "a"]))
    assert summary["provider_segment_count"] == 3
    assert summary["source_homogeneous"] is False


def test_segment_ids_deterministic():
    first = build_provider_segments(_manifest(["a", "b", "a"]))
    second = build_provider_segments(_manifest(["a", "b", "a"]))
    assert [row["segment_id"] for row in first] == [row["segment_id"] for row in second]
