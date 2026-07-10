from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "tools/audit_analytical_continuity.py"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sample_json_cli_is_read_only_and_reports_continuity() -> None:
    result = run_cli("--source", "SAMPLE", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["network_used"] is False
    assert payload["continuity_summary"]["continuity_segment_count"] >= 1
    assert "sample_synthetic_demo_contract" in payload["continuity_summary"]["provider_contract_counts"]
    assert payload["theme_robustness_continuity_universe_consistent"] is True


def test_cli_text_output_has_no_forbidden_wording() -> None:
    result = run_cli("--source", "SAMPLE")
    assert result.returncode == 0
    assert "Analytical continuity audit" in result.stdout
    assert "未来会涨" not in result.stdout
