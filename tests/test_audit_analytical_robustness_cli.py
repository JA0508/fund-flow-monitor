from __future__ import annotations

import json
import subprocess
import sys


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/audit_analytical_robustness.py", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_theme_json_audit_outputs_specification_results():
    result = _run(["--source-mode", "SAMPLE", "--theme", "半导体/芯片链", "--bucket-minutes", "1,5", "--json"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    evidence = payload["theme_robustness"]
    assert evidence["evaluated_specification_count"] == 2
    assert evidence["specification_results"]
    assert evidence["default_specification"]["specification_id"]


def test_pair_json_audit_outputs_denominator_fields():
    result = _run(
        [
            "--source-mode",
            "SAMPLE",
            "--pair",
            "AI算力/TMT::半导体/芯片链",
            "--bucket-minutes",
            "1,5",
            "--date-concentration",
            "--json",
        ]
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    evidence = payload["relationship_robustness"]
    first = evidence["specification_results"][0]
    assert first["aligned_observation_count"] >= 0
    assert "same_sign_count" in first
    assert first["per_date_results"]


def test_all_modes_output_is_not_mode_ranking():
    result = _run(["--source-mode", "SAMPLE", "--theme", "半导体/芯片链", "--all-modes", "--bucket-minutes", "1"])
    assert result.returncode == 0
    assert "Calculation-scope sensitivity" in result.stdout
    assert "not ranked" in result.stdout


def test_materialization_policy_audit_runs():
    result = _run(["--source-mode", "SAMPLE", "--theme", "半导体/芯片链", "--bucket-minutes", "1", "--materialization-policies", "--json"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["theme_robustness"]["evaluated_specification_count"] == 2


def test_missing_real_cache_is_safe(tmp_path):
    result = _run(["--source-mode", "REAL", "--theme", "半导体/芯片链", "--data-dir", str(tmp_path), "--bucket-minutes", "1", "--json"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["theme_robustness"]["specification_results"][0]["observation_count"] == 0


def test_invalid_pair_syntax_returns_error():
    result = _run(["--source-mode", "SAMPLE", "--pair", "badpair", "--json"])
    assert result.returncode == 2
    assert "Invalid --pair syntax" in result.stderr
