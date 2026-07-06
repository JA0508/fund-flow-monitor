from __future__ import annotations

import json
import subprocess
import sys


def test_audit_theme_taxonomy_cli_json() -> None:
    result = subprocess.run(
        [sys.executable, "tools/audit_theme_taxonomy.py", "--source-mode", "SAMPLE", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["source_mode"] == "SAMPLE"
    assert payload["theme_count"] == 8
    assert payload["coverage"]["unique_source_row_count"] == 20


def test_audit_theme_taxonomy_cli_coverage_overlap_theme() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "tools/audit_theme_taxonomy.py",
            "--source-mode",
            "SAMPLE",
            "--coverage",
            "--overlap",
            "--top-overlaps",
            "3",
            "--theme",
            "半导体/芯片链",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Theme taxonomy audit" in result.stdout
    assert "Coverage audit" in result.stdout
    assert "Cross-theme overlap" in result.stdout
    assert "Theme calibration: 半导体/芯片链" in result.stdout


def test_audit_theme_taxonomy_cli_unknown_theme_exits_nonzero() -> None:
    result = subprocess.run(
        [sys.executable, "tools/audit_theme_taxonomy.py", "--source-mode", "SAMPLE", "--theme", "不存在主题"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "unknown theme" in result.stdout
