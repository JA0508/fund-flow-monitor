from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd

from tools.inspect_history_evidence import inspect_history_evidence


def _write_snapshot(path, date: str = "2026-01-01") -> None:
    pd.DataFrame(
        [
            {
                "trade_date": date,
                "captured_at": f"{date} 09:30:00",
                "captured_time": "09:30:00",
                "sector_type": "行业资金流",
                "sector_name": "半导体",
                "main_net_inflow_billion": 12.3,
                "source": "REAL",
                "provider": "AKShare / Eastmoney",
                "api_name": "stock_sector_fund_flow_rank",
                "data_mode": "REAL",
                "fetched_at": f"{date} 09:30:00",
            }
        ]
    ).to_csv(path, index=False)


def test_inspect_history_evidence_function(tmp_path) -> None:
    _write_snapshot(tmp_path / "sector_flow_2026-01-01.csv")
    report = inspect_history_evidence(str(tmp_path), source_mode="REAL", selected_date="2026-01-01")
    assert report["manifest_row_count"] == 1
    assert report["summary"]["valid_snapshot_count"] == 1
    assert report["replay_evidence"]["evidence_state"] == "available"
    assert report["forbidden_hits"] == []


def test_inspect_history_evidence_empty_dir(tmp_path) -> None:
    report = inspect_history_evidence(str(tmp_path), source_mode="REAL")
    assert report["manifest_row_count"] == 0
    assert report["readiness"]["readiness_state"] == "no_real_history"


def test_inspect_history_evidence_cli_json(tmp_path) -> None:
    _write_snapshot(tmp_path / "sector_flow_2026-01-01.csv")
    result = subprocess.run(
        [
            sys.executable,
            "tools/inspect_history_evidence.py",
            "--data-dir",
            str(tmp_path),
            "--date",
            "2026-01-01",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["manifest_row_count"] == 1
    assert payload["replay_evidence"]["selected_trade_date"] == "2026-01-01"


def test_inspect_history_evidence_cli_matrix(tmp_path) -> None:
    _write_snapshot(tmp_path / "sector_flow_2026-01-01.csv")
    result = subprocess.run(
        [
            sys.executable,
            "tools/inspect_history_evidence.py",
            "--data-dir",
            str(tmp_path),
            "--matrix",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "coverage_matrix" in result.stdout
    assert "09:30" in result.stdout
