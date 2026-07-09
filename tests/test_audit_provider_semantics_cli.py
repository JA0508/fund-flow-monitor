from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "tools/audit_provider_semantics.py"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_registry_json_cli():
    result = run_cli("--registry", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["registry_summary"]["candidate_count"] >= 1
    assert payload["network_used"] is False


def test_primary_contract_cli():
    result = run_cli("--primary")
    assert result.returncode == 0
    assert "stock_sector_fund_flow_rank" in result.stdout


def test_candidate_compare_cli():
    result = run_cli("--compare", "akshare_eastmoney_sector_fund_flow_rank_today_industry::akshare_eastmoney_main_fund_flow_stock_universe", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["comparability"]["comparability_state"] == "non_equivalent"


def test_unknown_candidate_cli():
    result = run_cli("--candidate", "missing_provider", "--json")
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["errors"]


def test_eligibility_cli_has_no_fallback_by_default():
    result = run_cli("--eligibility", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert all(row["fallback_enabled"] is False for row in payload["eligibility"])
