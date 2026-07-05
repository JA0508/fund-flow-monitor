from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.providers.akshare_sector_flow import ProviderBoundaryError, ProviderFetchResult, build_provider_diagnostic
from src.storage import append_snapshot_safely
from tools import collect_market_snapshot


def _snapshot_df(captured_time: str = "10:00:00") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "trade_date": ["2026-06-01", "2026-06-01"],
            "captured_at": ["2026-06-01 10:00:00", "2026-06-01 10:00:00"],
            "captured_time": [captured_time, captured_time],
            "sector_type": ["行业资金流", "行业资金流"],
            "sector_code": ["BK001", "BK002"],
            "sector_name": ["半导体", "银行"],
            "change_pct": [1.2, -0.8],
            "main_net_inflow_yuan": [1_000_000_000, -500_000_000],
            "main_net_inflow_billion": [10.0, -5.0],
            "source": ["AKShare / Eastmoney", "AKShare / Eastmoney"],
            "provider": ["AKShare / Eastmoney", "AKShare / Eastmoney"],
            "api_name": ["stock_sector_fund_flow_rank", "stock_sector_fund_flow_rank"],
            "data_mode": ["REAL", "REAL"],
            "fetched_at": ["2026-06-01 10:00:00", "2026-06-01 10:00:00"],
        }
    )


def _collector_args(**overrides) -> argparse.Namespace:
    values = {
        "dry_run": False,
        "output_dir": "",
        "force": False,
        "quiet": True,
        "no_network": False,
        "no_log": False,
        "log_path": "",
        "sector_type": "行业资金流",
        "fetch_attempts": 1,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _raw_sector_flow() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "板块代码": ["BK001", "BK002"],
            "板块名称": ["半导体", "银行"],
            "涨跌幅": [1.2, -0.8],
            "主力净流入-净额": [100_000_000, -50_000_000],
            "主力净流入-净占比": [2.5, -1.1],
        }
    )


def test_collect_market_snapshot_can_be_imported():
    assert hasattr(collect_market_snapshot, "build_parser")
    assert hasattr(collect_market_snapshot, "collect_once")


def test_parser_accepts_expected_flags():
    parser = collect_market_snapshot.build_parser()
    args = parser.parse_args(["--dry-run", "--output-dir", "tmp", "--force", "--quiet", "--no-network", "--no-log", "--log-path", "tmp/log.jsonl", "--fetch-attempts", "2"])
    assert args.dry_run is True
    assert args.output_dir == "tmp"
    assert args.force is True
    assert args.quiet is True
    assert args.no_network is True
    assert args.no_log is True
    assert args.log_path == "tmp/log.jsonl"
    assert args.fetch_attempts == 2


def _provider_result(raw: pd.DataFrame | None = None, normalized: pd.DataFrame | None = None) -> ProviderFetchResult:
    raw_df = raw if raw is not None else _raw_sector_flow()
    normalized_df = normalized if normalized is not None else _snapshot_df()
    return ProviderFetchResult(
        raw_df=raw_df,
        normalized_df=normalized_df,
        diagnostic=build_provider_diagnostic(
            sector_type="行业资金流",
            indicator="今日",
            response=raw_df,
            normalization_status="success",
            message="mock provider result",
        ),
    )


def test_no_network_mode_does_not_fetch_or_write(tmp_path):
    args = _collector_args(output_dir=str(tmp_path), no_network=True)
    result = collect_market_snapshot.collect_once(args)
    assert result["status"] == "no_network"
    assert result["fetch_status"] == "skipped_no_network"
    assert result["write_status"] == "not_run"
    assert not list(tmp_path.glob("*.csv"))


def test_dry_run_mode_does_not_write_file(monkeypatch, tmp_path):
    monkeypatch.setattr(collect_market_snapshot, "fetch_and_normalize_sector_flow", lambda **kwargs: _provider_result())
    args = _collector_args(dry_run=True, output_dir=str(tmp_path))
    result = collect_market_snapshot.collect_once(args)
    assert result["status"] == "dry_run"
    assert result["fetch_status"] == "success"
    assert result["write_status"] == "dry_run"
    assert result["data_mode"] == "REAL"
    assert result["provider"] == "AKShare / Eastmoney"
    assert result["api_name"] == "stock_sector_fund_flow_rank"
    assert result["contract_ok"] is True
    assert result["contract_label"] == "真实数据契约通过"
    assert not list(tmp_path.glob("*.csv"))


def test_successful_mocked_fetch_writes_csv_and_audit_log(monkeypatch, tmp_path):
    monkeypatch.setattr(collect_market_snapshot, "fetch_and_normalize_sector_flow", lambda **kwargs: _provider_result())
    log_path = tmp_path / "logs/collector_runs.jsonl"
    args = _collector_args(output_dir=str(tmp_path / "ticks"), log_path=str(log_path))
    result = collect_market_snapshot.run_collector(args)
    assert result["status"] == "success"
    assert result["write_status"] == "written"
    assert result["log_status"] == "written"
    assert list((tmp_path / "ticks").glob("sector_flow_*.csv"))
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 1
    assert entries[0]["status"] == "success"
    assert entries[0]["provider"] == "AKShare / Eastmoney"


def test_no_log_disables_audit_log(monkeypatch, tmp_path):
    monkeypatch.setattr(collect_market_snapshot, "fetch_and_normalize_sector_flow", lambda **kwargs: _provider_result())
    log_path = tmp_path / "logs/collector_runs.jsonl"
    args = _collector_args(output_dir=str(tmp_path / "ticks"), log_path=str(log_path), no_log=True)
    result = collect_market_snapshot.run_collector(args)
    assert result["status"] == "success"
    assert result["log_status"] == "disabled"
    assert not log_path.exists()


def test_empty_fetch_classification(monkeypatch, tmp_path):
    def fake_fetch(**kwargs):
        diagnostic = build_provider_diagnostic(sector_type="行业资金流", indicator="今日", response=pd.DataFrame())
        raise ProviderBoundaryError("AKShare 返回空 DataFrame。", "empty_response", diagnostic=diagnostic)

    monkeypatch.setattr(collect_market_snapshot, "fetch_and_normalize_sector_flow", fake_fetch)
    args = _collector_args(output_dir=str(tmp_path))
    result = collect_market_snapshot.collect_once(args)
    assert result["status"] == "empty_fetch"
    assert result["error_category"] == "empty_response"
    assert result["write_status"] == "not_written"


def test_fetch_error_classification(monkeypatch, tmp_path):
    def fake_fetch(**kwargs):
        diagnostic = build_provider_diagnostic(sector_type="行业资金流", indicator="今日", error_category="network_error")
        raise ProviderBoundaryError("network unavailable", "network_error", diagnostic=diagnostic)

    monkeypatch.setattr(collect_market_snapshot, "fetch_and_normalize_sector_flow", fake_fetch)
    args = _collector_args(output_dir=str(tmp_path))
    result = collect_market_snapshot.collect_once(args)
    assert result["status"] == "fetch_error"
    assert result["error_category"] == "network_error"


def test_schema_drift_classification_is_not_generic_fetch(monkeypatch, tmp_path):
    def fake_fetch(**kwargs):
        raw = pd.DataFrame({"未知列": [1]})
        diagnostic = build_provider_diagnostic(
            sector_type="行业资金流",
            indicator="今日",
            response=raw,
            normalization_status="schema_drift",
            error_category="schema_drift",
        )
        raise ProviderBoundaryError("AKShare 返回 schema 缺少必要列映射。", "schema_drift", diagnostic=diagnostic)

    monkeypatch.setattr(collect_market_snapshot, "fetch_and_normalize_sector_flow", fake_fetch)
    args = _collector_args(output_dir=str(tmp_path))
    result = collect_market_snapshot.collect_once(args)
    assert result["status"] == "fetch_error"
    assert result["error_category"] == "schema_drift"
    assert result["normalization_status"] == "schema_drift"
    assert result["provider_columns"] == ["未知列"]


def test_contract_error_classification_blocks_write(monkeypatch, tmp_path):
    monkeypatch.setattr(collect_market_snapshot, "fetch_and_normalize_sector_flow", lambda **kwargs: _provider_result())
    monkeypatch.setattr(
        collect_market_snapshot,
        "validate_real_snapshot_dataframe",
        lambda df, context="real": {
            "contract_ok": False,
            "contract_label": "真实数据契约不通过",
            "warnings": [],
            "errors": ["forced contract error"],
        },
    )
    args = _collector_args(output_dir=str(tmp_path))
    result = collect_market_snapshot.collect_once(args)
    assert result["status"] == "contract_error"
    assert result["write_status"] == "not_written"
    assert not list(tmp_path.glob("*.csv"))


def test_duplicate_write_is_classified(monkeypatch, tmp_path):
    fixed_now = pd.Timestamp("2026-06-01 10:00:00", tz="Asia/Shanghai")
    monkeypatch.setattr(collect_market_snapshot, "get_china_now", lambda: fixed_now)
    monkeypatch.setattr(collect_market_snapshot, "fetch_and_normalize_sector_flow", lambda **kwargs: _provider_result())
    args = _collector_args(output_dir=str(tmp_path))
    first = collect_market_snapshot.collect_once(args)
    second = collect_market_snapshot.collect_once(args)
    assert first["status"] == "success"
    assert second["status"] == "duplicate_skipped"
    assert second["write_status"] == "skipped_duplicate"


def test_collect_real_snapshot_wrapper_imports():
    from tools import collect_real_snapshot

    assert collect_real_snapshot.main is collect_market_snapshot.main


def test_collect_real_snapshot_script_no_network_runs_without_writing(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "tools/collect_real_snapshot.py",
            "--no-network",
            "--output-dir",
            str(tmp_path),
            "--log-path",
            str(tmp_path / "collector_runs.jsonl"),
            "--quiet",
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0
    assert not list(tmp_path.glob("*.csv"))
    assert (tmp_path / "collector_runs.jsonl").exists()


def test_append_snapshot_safely_prevents_duplicate_writes(tmp_path):
    path = tmp_path / "sector_flow_2026-06-01.csv"
    first = append_snapshot_safely(_snapshot_df(), str(path))
    second = append_snapshot_safely(_snapshot_df(), str(path))
    assert first["written_rows"] == 2
    assert second["duplicate_detected"] is True
    assert second["written_rows"] == 0
    assert len(pd.read_csv(path)) == 2


def test_append_snapshot_safely_force_allows_duplicates(tmp_path):
    path = tmp_path / "sector_flow_2026-06-01.csv"
    append_snapshot_safely(_snapshot_df(), str(path))
    result = append_snapshot_safely(_snapshot_df(), str(path), force=True)
    assert result["written_rows"] == 2
    assert len(pd.read_csv(path)) == 4


def test_append_snapshot_safely_writes_only_tmp_path(tmp_path):
    path = tmp_path / "nested/sector_flow_2026-06-01.csv"
    result = append_snapshot_safely(_snapshot_df(), str(path))
    assert result["write_status"] == "written"
    assert path.exists()


def test_append_snapshot_safely_blocks_sample_and_demo(tmp_path):
    sample_df = _snapshot_df()
    sample_df["source"] = "SAMPLE"
    result = append_snapshot_safely(sample_df, str(tmp_path / "sector_flow_2026-06-01.csv"))
    assert result["write_status"] == "blocked"
    assert result["errors"]
    assert not list(tmp_path.glob("*.csv"))
