from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.evidence_accumulation import (
    ASSIGNMENT_OUTSIDE,
    ASSIGNMENT_DATE_INELIGIBLE,
    CONTRIBUTION_ADDITIONAL,
    CONTRIBUTION_EXCLUDED,
    CONTRIBUTION_NEW_CELL,
    build_acquisition_frame,
    build_acquisition_frame_id,
    build_evidence_accumulation_report,
    build_physical_capture_event_inventory,
    validate_evidence_accumulation_text,
)
from src.market_session_policy import build_declared_market_session_policy
from src.market_session_policy import reconcile_exchange_session_domains
from src.providers.akshare_sector_flow import normalize_provider_dataframe
from src.theme_dynamics import get_canonical_materialization_policy


def _raw_provider_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "序号": [1, 2],
            "板块代码": ["BK001", "BK002"],
            "名称": ["半导体", "通信"],
            "今日涨跌幅": [1.2, -0.3],
            "今日主力净流入-净额": [100_000_000, -50_000_000],
            "今日主力净流入-净占比": [3.2, -1.1],
            "今日超大单净流入-净额": [50_000_000, -20_000_000],
            "今日大单净流入-净额": [30_000_000, -10_000_000],
            "今日中单净流入-净额": [10_000_000, -10_000_000],
            "今日小单净流入-净额": [10_000_000, -10_000_000],
            "今日主力净流入最大股": ["样例A", "样例B"],
            "今日主力净流入最大股代码": ["000001", "000002"],
        }
    )


def _write_provider_snapshots(tmp_path, times: list[str], trade_date: str = "2026-06-10") -> None:
    frames = []
    for time_text in times:
        captured_at = datetime.fromisoformat(f"{trade_date}T{time_text}+08:00")
        result = normalize_provider_dataframe(_raw_provider_frame(), sector_type="行业资金流", captured_at=captured_at)
        frames.append(result.normalized_df)
    out = pd.concat(frames, ignore_index=True)
    (tmp_path / f"sector_flow_{trade_date}.csv").write_text(out.to_csv(index=False), encoding="utf-8")


def _market_policy(*, eligible_dates=("2026-06-10",), coverage_start="2026-06-10", coverage_end="2026-06-10"):
    return build_declared_market_session_policy(
        eligible_dates=list(eligible_dates),
        coverage_start=coverage_start,
        coverage_end=coverage_end,
    )


def _write_legacy_snapshot(tmp_path, time_text: str = "10:00:00", trade_date: str = "2026-06-10") -> None:
    captured_at = datetime.fromisoformat(f"{trade_date}T{time_text}+08:00")
    result = normalize_provider_dataframe(_raw_provider_frame(), sector_type="行业资金流", captured_at=captured_at)
    df = result.normalized_df
    df = df.drop(
        columns=[
            "provider_contract_id",
            "provider_contract_fingerprint",
            "provider_id",
            "upstream_origin",
            "provider",
            "api_name",
        ],
        errors="ignore",
    )
    (tmp_path / f"sector_flow_{trade_date}.csv").write_text(df.to_csv(index=False), encoding="utf-8")


def test_physical_capture_inventory_is_one_row_per_capture_not_sector_row(tmp_path):
    _write_provider_snapshots(tmp_path, ["10:00:00", "10:05:00", "10:40:00"])
    inventory = build_physical_capture_event_inventory(tmp_path, source_mode="REAL", market_session_policy=_market_policy())
    assert len(inventory) == 3
    assert inventory["row_count"].tolist() == [2, 2, 2]
    assert inventory["is_qualified_acquisition_event"].tolist() == [True, True, True]


def test_provider_normalization_trade_date_is_capture_derived():
    captured_at = datetime.fromisoformat("2026-06-11T10:00:00+08:00")
    result = normalize_provider_dataframe(_raw_provider_frame(), sector_type="行业资金流", captured_at=captured_at)
    df = result.normalized_df
    assert df["captured_at"].astype(str).str.startswith("2026-06-11 10:00:00").all()
    assert df["captured_time"].unique().tolist() == ["10:00:00"]
    assert df["trade_date"].unique().tolist() == ["2026-06-11"]


def test_acquisition_frame_identity_is_deterministic_and_separate_from_canonical_policy():
    frame_id_a = build_acquisition_frame_id(cell_minutes=30)
    frame_id_b = build_acquisition_frame_id(cell_minutes=30)
    frame_id_c = build_acquisition_frame_id(cell_minutes=15)
    policy_a = _market_policy(eligible_dates=("2026-06-10",), coverage_start="2026-06-10", coverage_end="2026-06-10")
    policy_b = _market_policy(eligible_dates=("2026-06-11",), coverage_start="2026-06-11", coverage_end="2026-06-11")
    assert frame_id_a == frame_id_b
    assert frame_id_a != frame_id_c
    assert policy_a["calendar_policy_identity"] != policy_b["calendar_policy_identity"]
    assert get_canonical_materialization_policy() == "latest_valid_snapshot_in_bucket"


def test_session_boundary_assignment_and_off_frame_capture(tmp_path):
    _write_provider_snapshots(tmp_path, ["09:30:00", "11:30:00", "12:00:00"])
    report = build_evidence_accumulation_report("REAL", data_dir=tmp_path, cell_minutes=30, market_session_policy=_market_policy())
    preview = report["events_preview"]
    assert preview[0]["marginal_coverage_contribution"] == CONTRIBUTION_NEW_CELL
    assert preview[1]["marginal_coverage_contribution"] == CONTRIBUTION_NEW_CELL
    assert preview[2]["acquisition_assignment_state"] == ASSIGNMENT_OUTSIDE


def test_provider_normalization_to_accumulation_handshake(tmp_path):
    _write_provider_snapshots(tmp_path, ["10:00:00", "10:05:00", "10:40:00"])
    report = build_evidence_accumulation_report("REAL", data_dir=tmp_path, cell_minutes=30, market_session_policy=_market_policy())
    assert report["physical_capture_event_count"] == 3
    assert report["qualified_capture_event_count"] == 3
    assert report["covered_acquisition_cell_count"] == 2
    counts = report["marginal_contribution_counts"]
    assert counts[CONTRIBUTION_NEW_CELL] == 2
    assert counts[CONTRIBUTION_ADDITIONAL] == 1


def test_legacy_unresolved_capture_visible_but_excluded(tmp_path):
    _write_legacy_snapshot(tmp_path)
    report = build_evidence_accumulation_report("REAL", data_dir=tmp_path, cell_minutes=30, market_session_policy=_market_policy())
    assert report["physical_capture_event_count"] == 1
    assert report["qualified_capture_event_count"] == 0
    assert report["excluded_capture_event_count"] == 1
    assert report["provider_contract_resolution_counts"] == {"unknown": 1}
    assert report["marginal_contribution_counts"][CONTRIBUTION_EXCLUDED] == 1


def test_clustered_captures_cover_one_cell(tmp_path):
    times = [f"10:{minute:02d}:00" for minute in range(10)]
    _write_provider_snapshots(tmp_path, times)
    report = build_evidence_accumulation_report("REAL", data_dir=tmp_path, cell_minutes=30, market_session_policy=_market_policy())
    assert report["qualified_capture_event_count"] == 10
    assert report["covered_acquisition_cell_count"] == 1
    assert report["marginal_contribution_counts"][CONTRIBUTION_NEW_CELL] == 1
    assert report["marginal_contribution_counts"][CONTRIBUTION_ADDITIONAL] == 9


def test_equal_capture_count_can_have_different_cell_coverage(tmp_path):
    clustered = tmp_path / "clustered"
    distributed = tmp_path / "distributed"
    clustered.mkdir()
    distributed.mkdir()
    _write_provider_snapshots(clustered, [f"10:{minute:02d}:00" for minute in range(10)])
    _write_provider_snapshots(
        distributed,
        ["09:35:00", "10:05:00", "10:35:00", "11:05:00", "13:05:00", "13:35:00", "14:05:00", "14:35:00", "14:45:00", "14:55:00"],
    )
    clustered_report = build_evidence_accumulation_report("REAL", data_dir=clustered, cell_minutes=30, market_session_policy=_market_policy())
    distributed_report = build_evidence_accumulation_report("REAL", data_dir=distributed, cell_minutes=30, market_session_policy=_market_policy())
    assert clustered_report["qualified_capture_event_count"] == distributed_report["qualified_capture_event_count"] == 10
    assert clustered_report["covered_acquisition_cell_count"] < distributed_report["covered_acquisition_cell_count"]


def test_sample_is_demo_eligible_but_not_real_accumulation(tmp_path):
    _write_provider_snapshots(tmp_path, ["10:00:00"])
    df = pd.read_csv(tmp_path / "sector_flow_2026-06-10.csv")
    df["source"] = "SAMPLE"
    df["data_mode"] = "SAMPLE"
    df = df.drop(columns=["provider_contract_id", "provider_contract_fingerprint"], errors="ignore")
    (tmp_path / "sector_flow_2026-06-10.csv").write_text(df.to_csv(index=False), encoding="utf-8")
    sample_report = build_evidence_accumulation_report("SAMPLE", data_dir=tmp_path, cell_minutes=30)
    real_report = build_evidence_accumulation_report("REAL", data_dir=tmp_path, cell_minutes=30, market_session_policy=_market_policy())
    assert sample_report["qualified_capture_event_count"] == 1
    assert real_report["qualified_capture_event_count"] == 0


def test_mixed_legacy_and_verified_history_preserves_both_universes(tmp_path):
    verified_dir = tmp_path / "verified"
    legacy_dir = tmp_path / "legacy"
    verified_dir.mkdir()
    legacy_dir.mkdir()
    _write_provider_snapshots(verified_dir, ["10:00:00", "10:40:00"])
    _write_legacy_snapshot(legacy_dir, time_text="10:05:00")
    verified = pd.read_csv(verified_dir / "sector_flow_2026-06-10.csv")
    legacy = pd.read_csv(legacy_dir / "sector_flow_2026-06-10.csv")
    mixed = pd.concat([verified, legacy], ignore_index=True)
    (tmp_path / "sector_flow_2026-06-10.csv").write_text(mixed.to_csv(index=False), encoding="utf-8")

    report = build_evidence_accumulation_report("REAL", data_dir=tmp_path, cell_minutes=30, market_session_policy=_market_policy())
    assert report["physical_capture_event_count"] == 3
    assert report["qualified_capture_event_count"] == 2
    assert report["excluded_capture_event_count"] == 1
    assert report["covered_acquisition_cell_count"] == 2
    assert report["provider_contract_resolution_counts"]["explicit_verified"] == 2
    assert report["provider_contract_resolution_counts"]["unknown"] == 1
    assert report["excluded_reason_counts"]["unresolved_provider_contract"] == 1


def test_clock_window_capture_on_ineligible_date_does_not_qualify(tmp_path):
    _write_provider_snapshots(tmp_path, ["10:00:00"], trade_date="2026-06-11")
    policy = _market_policy(eligible_dates=("2026-06-10",), coverage_start="2026-06-10", coverage_end="2026-06-11")
    report = build_evidence_accumulation_report("REAL", data_dir=tmp_path, cell_minutes=30, market_session_policy=policy)
    assert report["physical_capture_event_count"] == 1
    assert report["qualified_capture_event_count"] == 0
    assert report["target_acquisition_cell_count"] == 0
    assert report["coverage_denominator"] == 0
    assert report["events_preview"][0]["market_session_date_state"] == "market_session_date_ineligible"
    assert report["events_preview"][0]["acquisition_assignment_state"] == ASSIGNMENT_DATE_INELIGIBLE
    assert report["excluded_reason_counts"]["market_session_date_ineligible"] == 1


def test_offline_contamination_regression_keeps_ineligible_capture_visible(tmp_path):
    _write_provider_snapshots(tmp_path, ["10:00:00"], trade_date="2026-06-10")
    _write_provider_snapshots(tmp_path, ["10:00:00"], trade_date="2026-06-11")
    policy = _market_policy(eligible_dates=("2026-06-10",), coverage_start="2026-06-10", coverage_end="2026-06-11")
    report = build_evidence_accumulation_report("REAL", data_dir=tmp_path, cell_minutes=30, market_session_policy=policy)
    assert report["physical_capture_event_count"] == 2
    assert report["qualified_capture_event_count"] == 1
    assert report["covered_acquisition_cell_count"] == 1
    assert report["target_acquisition_cell_count"] == 8
    assert report["market_session_date_ineligible_capture_count"] == 1
    states = {item["trade_date"]: item["market_session_date_state"] for item in report["events_preview"]}
    assert states == {
        "2026-06-10": "eligible_market_session_date",
        "2026-06-11": "market_session_date_ineligible",
    }


def test_evidence_report_exposes_calendar_policy_denominator_provenance(tmp_path):
    _write_provider_snapshots(tmp_path, ["10:00:00"], trade_date="2026-06-10")
    policy = _market_policy(eligible_dates=("2026-06-10",), coverage_start="2026-06-10", coverage_end="2026-06-11")
    report = build_evidence_accumulation_report("REAL", data_dir=tmp_path, cell_minutes=30, market_session_policy=policy)
    assert report["market_session_policy_id"] == policy["calendar_policy_identity"]
    assert report["market_session_date_policy"]["calendar_policy_identity"] == policy["calendar_policy_identity"]
    assert report["qualified_target_dates"] == ["2026-06-10"]
    assert report["qualified_target_date_count"] == 1
    assert report["target_cells_by_date"] == {"2026-06-10": 8}


def test_cross_exchange_reconciled_policy_keeps_only_common_eligible_date_in_denominator(tmp_path):
    _write_provider_snapshots(tmp_path, ["10:00:00"], trade_date="2026-06-10")
    _write_provider_snapshots(tmp_path, ["10:00:00"], trade_date="2026-06-11")
    _write_provider_snapshots(tmp_path, ["10:00:00"], trade_date="2026-07-01")
    reconciliation = reconcile_exchange_session_domains(
        ["2026-06-10", "2026-06-11"],
        ["2026-06-10"],
        coverage_start="2026-06-10",
        coverage_end="2026-06-11",
    )
    policy = build_declared_market_session_policy(
        eligible_dates=reconciliation["common_eligible_dates"],
        coverage_start=reconciliation["overlapping_coverage_start"],
        coverage_end=reconciliation["overlapping_coverage_end"],
        calendar_source="unit_test_cross_exchange_reconciled_dates",
        calendar_source_identity="unit_test_cross_exchange_reconciled_dates_v1",
    )
    policy["cross_exchange_alignment_state"] = reconciliation["cross_exchange_alignment_state"]
    report = build_evidence_accumulation_report("REAL", data_dir=tmp_path, cell_minutes=30, market_session_policy=policy)
    assert report["physical_capture_event_count"] == 3
    assert report["qualified_capture_event_count"] == 1
    assert report["qualified_target_dates"] == ["2026-06-10"]
    assert report["target_cells_by_date"] == {"2026-06-10": 8}
    assert report["closed_or_ineligible_represented_dates"] == ["2026-06-11"]
    assert report["unverified_represented_dates"] == ["2026-07-01"]
    assert report["coverage_denominator"] == 8


def test_validate_evidence_accumulation_text_detects_forbidden_words():
    assert "未来会涨" in validate_evidence_accumulation_text("未来会涨")
    assert validate_evidence_accumulation_text("Capture count and cell coverage are separate.") == []
