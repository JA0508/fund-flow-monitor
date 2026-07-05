from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.providers.akshare_sector_flow import ProviderFetchResult, build_provider_diagnostic
from tools import probe_akshare


def test_probe_run_json_result_with_mock(monkeypatch):
    raw = pd.DataFrame({"名称": ["半导体"], "今日主力净流入-净额": [100_000_000]})
    normalized = pd.DataFrame(
        {
            "captured_time": ["10:00:00"],
            "sector_type": ["行业资金流"],
            "sector_name": ["半导体"],
            "main_net_inflow_billion": [1.0],
            "source": ["AKShare / Eastmoney"],
            "provider": ["AKShare / Eastmoney"],
            "api_name": ["stock_sector_fund_flow_rank"],
            "data_mode": ["REAL"],
            "fetched_at": ["2026-06-01T10:00:00+08:00"],
        }
    )

    monkeypatch.setattr(
        probe_akshare,
        "fetch_and_normalize_sector_flow",
        lambda **kwargs: ProviderFetchResult(
            raw_df=raw,
            normalized_df=normalized,
            diagnostic=build_provider_diagnostic(
                sector_type="行业资金流",
                indicator="今日",
                response=raw,
                normalization_status="success",
            ),
        ),
    )
    result = probe_akshare.run_probe(argparse.Namespace(sector_type="行业资金流", indicator="今日", attempts=1))
    encoded = json.dumps(result, ensure_ascii=False)
    assert result["success"] is True
    assert "schema_fingerprint" in encoded


def test_probe_quiet_does_not_write_cache(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "tools/probe_akshare.py",
            "--quiet",
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert not list((project_root / "data/ticks").glob("probe_*.csv"))
    assert result.returncode in {0, 1}

