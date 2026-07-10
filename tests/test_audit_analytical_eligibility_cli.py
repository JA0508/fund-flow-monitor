from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "tools/audit_analytical_eligibility.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_audit_analytical_eligibility_sample_json() -> None:
    result = _run("--source", "SAMPLE", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    qualified = payload["availability_vs_qualified"]["qualified_summary"]
    assert payload["source_mode"] == "SAMPLE"
    assert payload["network_used"] is False
    assert qualified["eligible_observation_count"] > 0
    assert qualified["excluded_observation_count"] == 0


def test_audit_analytical_eligibility_real_empty_directory(tmp_path: Path) -> None:
    result = _run("--source", "REAL", "--data-dir", str(tmp_path), "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    qualified = payload["availability_vs_qualified"]["qualified_summary"]
    assert payload["source_mode"] == "REAL"
    assert payload["network_used"] is False
    assert payload["canonical_observation_count"] == 0
    assert qualified["qualified_readiness_state"] == "no_qualified_history"
