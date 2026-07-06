from __future__ import annotations

import json
import subprocess
import sys

from tools.inspect_theme_evidence import inspect_theme_evidence


def test_inspect_theme_evidence_function_sample() -> None:
    evidence = inspect_theme_evidence("半导体/芯片链", source_mode="SAMPLE")
    assert evidence["source_mode"] == "SAMPLE"
    assert evidence["theme_name"] == "半导体/芯片链"
    assert "taxonomy_fingerprint" in evidence


def test_inspect_theme_evidence_unknown_theme() -> None:
    evidence = inspect_theme_evidence("不存在主题", source_mode="SAMPLE")
    assert evidence["evidence_available"] is False
    assert "未知主题" in evidence["warnings"][0]


def test_inspect_theme_evidence_cli_json() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "tools/inspect_theme_evidence.py",
            "--theme",
            "半导体/芯片链",
            "--source-mode",
            "SAMPLE",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["source_mode"] == "SAMPLE"
    assert payload["theme_name"] == "半导体/芯片链"


def test_inspect_theme_evidence_cli_trace_members() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "tools/inspect_theme_evidence.py",
            "--theme",
            "半导体/芯片链",
            "--source-mode",
            "SAMPLE",
            "--trace",
            "--members",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Theme observation evidence" in result.stdout
    assert "Member contribution table" in result.stdout
    assert "SAMPLE" in result.stdout

