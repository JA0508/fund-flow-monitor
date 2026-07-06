from __future__ import annotations

import pandas as pd

from src.history_evidence import (
    build_coverage_matrix,
    build_historical_coverage_summary,
    build_snapshot_manifest,
    classify_historical_evidence_readiness,
    compute_file_sha256,
    inspect_snapshot_evidence,
    normalize_captured_time_bucket,
    resolve_replay_evidence,
    validate_history_evidence_text,
)


def _write_snapshot(path, date: str, times: list[str], source_mode: str = "REAL") -> None:
    rows = []
    for captured_time in times:
        for idx, sector in enumerate(["半导体", "银行"]):
            rows.append(
                {
                    "trade_date": date,
                    "captured_at": f"{date} {captured_time}",
                    "captured_time": captured_time,
                    "sector_type": "行业资金流",
                    "sector_name": sector,
                    "main_net_inflow_billion": 10 - idx,
                    "source": source_mode,
                    "provider": "AKShare / Eastmoney" if source_mode == "REAL" else "SAMPLE",
                    "api_name": "stock_sector_fund_flow_rank" if source_mode == "REAL" else "sample_data",
                    "data_mode": source_mode,
                    "fetched_at": f"{date} {captured_time}",
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False)


def test_normalize_captured_time_bucket() -> None:
    assert normalize_captured_time_bucket("09:31:45", bucket_minutes=5) == "09:30"
    assert normalize_captured_time_bucket("09:36:00", bucket_minutes=5) == "09:35"


def test_inspect_snapshot_evidence_real(tmp_path) -> None:
    path = tmp_path / "sector_flow_2026-01-01.csv"
    _write_snapshot(path, "2026-01-01", ["09:31:00", "09:35:00"])
    evidence = inspect_snapshot_evidence(path, cache_root=tmp_path, source_mode="REAL")
    assert evidence["is_readable"] is True
    assert evidence["contract_ok"] is True
    assert evidence["trade_date"] == "2026-01-01"
    assert evidence["captured_time_count"] == 2
    assert evidence["relative_path"] == "sector_flow_2026-01-01.csv"
    assert len(evidence["snapshot_id"]) == 20


def test_inspect_snapshot_evidence_sample_contract(tmp_path) -> None:
    path = tmp_path / "sector_flow_2026-01-02.csv"
    _write_snapshot(path, "2026-01-02", ["10:00:00"], source_mode="SAMPLE")
    evidence = inspect_snapshot_evidence(path, cache_root=tmp_path, source_mode="SAMPLE")
    assert evidence["contract_ok"] is True
    assert evidence["source_mode"] == "SAMPLE"
    assert evidence["data_mode"] == "SAMPLE"


def test_inspect_snapshot_evidence_malformed_csv(tmp_path) -> None:
    path = tmp_path / "sector_flow_2026-01-03.csv"
    path.write_text('captured_time,sector_name\n"unterminated', encoding="utf-8")
    evidence = inspect_snapshot_evidence(path, cache_root=tmp_path, source_mode="REAL")
    assert evidence["is_malformed"] is True
    assert evidence["errors"]


def test_compute_file_sha256_is_deterministic(tmp_path) -> None:
    path = tmp_path / "x.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    assert compute_file_sha256(path) == compute_file_sha256(path)


def test_build_snapshot_manifest_sorts_and_uses_relative_paths(tmp_path) -> None:
    _write_snapshot(tmp_path / "sector_flow_2026-01-02.csv", "2026-01-02", ["10:00:00"])
    _write_snapshot(tmp_path / "sector_flow_2026-01-01.csv", "2026-01-01", ["10:00:00"])
    manifest = build_snapshot_manifest(tmp_path, source_mode="REAL")
    assert manifest["trade_date"].tolist() == ["2026-01-01", "2026-01-02"]
    assert manifest["relative_path"].str.contains(str(tmp_path)).sum() == 0


def test_build_historical_coverage_summary() -> None:
    manifest = pd.DataFrame(
        [
            {
                "is_readable": True,
                "is_empty": False,
                "is_malformed": False,
                "trade_date": "2026-01-01",
                "captured_times": ["09:30:00", "09:31:00"],
                "captured_time_buckets": ["09:30", "09:31"],
                "provider": "AKShare / Eastmoney",
                "api_name": "stock_sector_fund_flow_rank",
                "source": "AKShare / Eastmoney",
                "data_mode": "REAL",
                "schema_fingerprint": "abc",
                "contract_ok": True,
            }
        ]
    )
    summary = build_historical_coverage_summary(manifest)
    assert summary["valid_snapshot_count"] == 1
    assert summary["trade_date_count"] == 1
    assert summary["schema_consistent"] is True
    assert summary["contract_pass_count"] == 1


def test_build_coverage_matrix_counts_buckets(tmp_path) -> None:
    _write_snapshot(tmp_path / "sector_flow_2026-01-01.csv", "2026-01-01", ["09:31:00", "09:35:00"])
    manifest = build_snapshot_manifest(tmp_path, source_mode="REAL")
    matrix = build_coverage_matrix(manifest)
    assert matrix.loc[0, "trade_date"] == "2026-01-01"
    assert int(matrix.loc[0, "09:31"]) == 1
    assert int(matrix.loc[0, "09:35"]) == 1


def test_classify_historical_evidence_readiness_states() -> None:
    empty = build_historical_coverage_summary(pd.DataFrame())
    assert classify_historical_evidence_readiness(empty)["readiness_state"] == "no_real_history"
    one = {
        "valid_snapshot_count": 1,
        "trade_date_count": 1,
        "captured_bucket_count_by_date": {"2026-01-01": 1},
        "snapshots_by_date": {"2026-01-01": 1},
    }
    assert classify_historical_evidence_readiness(one)["readiness_state"] == "single_snapshot"
    intraday = {**one, "captured_bucket_count_by_date": {"2026-01-01": 3}}
    assert classify_historical_evidence_readiness(intraday)["readiness_state"] == "single_day_intraday"
    multi = {
        "valid_snapshot_count": 3,
        "trade_date_count": 3,
        "captured_bucket_count_by_date": {"a": 1, "b": 1, "c": 1},
        "snapshots_by_date": {"a": 1, "b": 1, "c": 1},
    }
    assert classify_historical_evidence_readiness(multi)["readiness_state"] == "multi_day_ready"


def test_resolve_replay_evidence(tmp_path) -> None:
    _write_snapshot(tmp_path / "sector_flow_2026-01-01.csv", "2026-01-01", ["09:30:00", "10:00:00"])
    manifest = build_snapshot_manifest(tmp_path, source_mode="REAL")
    replay = resolve_replay_evidence("2026-01-01", manifest)
    assert replay["evidence_state"] == "available"
    assert replay["captured_time_start"] == "09:30:00"
    assert replay["captured_time_end"] == "10:00:00"
    assert replay["schema_consistent"] is True


def test_validate_history_evidence_text() -> None:
    assert "未来会涨" in validate_history_evidence_text("这里不能写未来会涨")
    assert validate_history_evidence_text("历史证据只描述 CSV 覆盖和回放来源。") == []
