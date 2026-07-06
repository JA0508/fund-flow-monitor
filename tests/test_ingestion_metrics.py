from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion_metrics import (
    assess_real_cache_coverage,
    build_collection_operations_status,
    build_ingestion_metrics,
    load_collector_audit_log,
    summarize_ingestion_metrics,
    validate_ingestion_metrics_text,
)


def _write_log(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-06-01T10:00:00+08:00","status":"success","rows":80,"written_rows":80,"trade_date":"2026-06-01","captured_time":"10:00:00","provider":"AKShare / Eastmoney","api_name":"stock_sector_fund_flow_rank"}',
                '{"timestamp":"2026-06-01T10:05:00+08:00","status":"duplicate_skipped","rows":80,"written_rows":0,"trade_date":"2026-06-01","captured_time":"10:05:00","provider":"AKShare / Eastmoney","api_name":"stock_sector_fund_flow_rank"}',
                '{"timestamp":"2026-06-01T10:10:00+08:00","status":"dry_run","rows":80,"written_rows":0,"trade_date":"2026-06-01","captured_time":"10:10:00"}',
                '{"timestamp":"2026-06-01T10:15:00+08:00","status":"no_network","rows":0,"written_rows":0}',
                '{"timestamp":"2026-06-01T10:20:00+08:00","status":"fetch_error","error_category":"network_error"}',
                "not-json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_snapshot(path: Path, date: str, times: list[str]) -> None:
    rows = []
    for idx, captured_time in enumerate(times):
        rows.append(
            {
                "trade_date": date,
                "captured_at": f"{date} {captured_time}",
                "captured_time": captured_time,
                "sector_type": "行业资金流",
                "sector_code": f"BK{idx:03d}",
                "sector_name": f"板块{idx}",
                "main_net_inflow_billion": float(idx),
                "source": "AKShare / Eastmoney",
                "provider": "AKShare / Eastmoney",
                "api_name": "stock_sector_fund_flow_rank",
                "data_mode": "REAL",
                "fetched_at": f"{date}T{captured_time}+08:00",
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def test_load_missing_audit_log_is_safe(tmp_path):
    report = load_collector_audit_log(tmp_path / "missing.jsonl")
    assert report["log_exists"] is False
    assert report["valid_log_records"] == 0


def test_ingestion_metrics_success_rate_denominator_excludes_dry_and_no_network(tmp_path):
    log_path = tmp_path / "collector_runs.jsonl"
    _write_log(log_path)
    metrics = build_ingestion_metrics(log_path, now="2026-06-01T12:00:00+08:00")
    assert metrics["total_runs"] == 5
    assert metrics["malformed_line_count"] == 1
    assert metrics["success_count"] == 1
    assert metrics["duplicate_skipped_count"] == 1
    assert metrics["dry_run_count"] == 1
    assert metrics["no_network_count"] == 1
    assert metrics["failure_count"] == 1
    assert metrics["write_intent_run_count"] == 3
    assert metrics["success_rate"] == round(1 / 3, 4)
    assert "dry_run and no_network excluded" in metrics["success_rate_denominator_semantics"]


def test_ingestion_metrics_summary_has_no_forbidden_words(tmp_path):
    log_path = tmp_path / "collector_runs.jsonl"
    _write_log(log_path)
    summary = summarize_ingestion_metrics(build_ingestion_metrics(log_path))
    assert validate_ingestion_metrics_text(summary) == []


def test_cache_coverage_no_real_data(tmp_path):
    coverage = assess_real_cache_coverage(tmp_path)
    assert coverage["coverage_label"] == "no_real_data"
    assert coverage["real_snapshot_count"] == 0


def test_cache_coverage_single_snapshot(tmp_path):
    _write_snapshot(tmp_path / "sector_flow_2026-06-01.csv", "2026-06-01", ["10:00:00"])
    coverage = assess_real_cache_coverage(tmp_path, now="2026-06-01T12:00:00+08:00")
    assert coverage["coverage_label"] == "single_snapshot"
    assert coverage["distinct_captured_times_today"] == 1


def test_cache_coverage_usable_intraday(tmp_path):
    _write_snapshot(
        tmp_path / "sector_flow_2026-06-01.csv",
        "2026-06-01",
        ["10:00:00", "10:05:00", "10:10:00"],
    )
    coverage = assess_real_cache_coverage(tmp_path, now="2026-06-01T12:00:00+08:00")
    assert coverage["coverage_label"] == "usable_intraday_coverage"
    assert coverage["enough_intraday_points"] is True


def test_operations_status_combines_policy_metrics_and_coverage(tmp_path):
    policy = {"eligible": True, "policy_status": "eligible", "policy_reason": "ok"}
    metrics = build_ingestion_metrics(tmp_path / "missing.jsonl")
    coverage = assess_real_cache_coverage(tmp_path)
    status = build_collection_operations_status(policy, metrics, coverage)
    assert status["operations_label"] == "可按需启动采集"
    assert status["policy_status"] == "eligible"
