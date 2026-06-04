from __future__ import annotations

import argparse

import pandas as pd

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
            "main_net_inflow_billion": [10.0, -5.0],
            "source": ["AKShare / Eastmoney", "AKShare / Eastmoney"],
        }
    )


def test_collect_market_snapshot_can_be_imported():
    assert hasattr(collect_market_snapshot, "build_parser")
    assert hasattr(collect_market_snapshot, "collect_once")


def test_parser_accepts_expected_flags():
    parser = collect_market_snapshot.build_parser()
    args = parser.parse_args(["--dry-run", "--output-dir", "tmp", "--force", "--quiet", "--no-network"])
    assert args.dry_run is True
    assert args.output_dir == "tmp"
    assert args.force is True
    assert args.quiet is True
    assert args.no_network is True


def test_no_network_mode_does_not_fetch_or_write(tmp_path):
    args = argparse.Namespace(
        dry_run=False,
        output_dir=str(tmp_path),
        force=False,
        quiet=True,
        no_network=True,
        sector_type="行业资金流",
    )
    result = collect_market_snapshot.collect_once(args)
    assert result["fetch_status"] == "skipped_no_network"
    assert result["write_status"] == "not_run"
    assert not list(tmp_path.glob("*.csv"))


def test_dry_run_mode_does_not_write_file(monkeypatch, tmp_path):
    def fake_fetch_sector_flow(sector_type: str, indicator: str = "今日"):
        return pd.DataFrame(
            {
                "板块代码": ["BK001"],
                "板块名称": ["半导体"],
                "涨跌幅": [1.2],
                "主力净流入-净额": [100_000_000],
                "主力净流入-净占比": [2.5],
            }
        )

    monkeypatch.setattr(collect_market_snapshot, "fetch_sector_flow", fake_fetch_sector_flow)
    args = argparse.Namespace(
        dry_run=True,
        output_dir=str(tmp_path),
        force=False,
        quiet=True,
        no_network=False,
        sector_type="行业资金流",
    )
    result = collect_market_snapshot.collect_once(args)
    assert result["fetch_status"] == "success"
    assert result["write_status"] == "dry_run"
    assert not list(tmp_path.glob("*.csv"))


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
