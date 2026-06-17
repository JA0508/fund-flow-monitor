from __future__ import annotations

import sys

from tools.quality_gate import (
    build_quality_gate_commands,
    filter_quality_gate_commands,
    run_quality_gate_command,
)


def test_build_quality_gate_commands_contains_expected_checks():
    commands = build_quality_gate_commands("python")
    names = [command["name"] for command in commands]
    assert names == [
        "pytest",
        "compileall",
        "release_check",
        "cloud_preflight",
        "public_demo_preflight",
        "smoke_check",
        "verify_runtime",
    ]


def test_public_demo_preflight_sets_env_flag():
    commands = build_quality_gate_commands("python")
    public_demo = next(command for command in commands if command["name"] == "public_demo_preflight")
    assert public_demo["env"] == {"FUND_FLOW_PUBLIC_DEMO": "1"}


def test_filter_quality_gate_commands_only_and_skip():
    commands = build_quality_gate_commands("python")
    filtered = filter_quality_gate_commands(commands, only=["pytest", "cloud_preflight"], skip=["pytest"])
    assert [command["name"] for command in filtered] == ["cloud_preflight"]


def test_run_quality_gate_command_success(tmp_path):
    spec = {
        "name": "tiny_success",
        "label": "tiny success",
        "command": [sys.executable, "-c", "print('ok')"],
        "env": {},
    }
    result = run_quality_gate_command(spec, project_root=tmp_path)
    assert result["ok"] is True
    assert result["returncode"] == 0
    assert "ok" in result["stdout"]


def test_run_quality_gate_command_failure(tmp_path):
    spec = {
        "name": "tiny_failure",
        "label": "tiny failure",
        "command": [sys.executable, "-c", "raise SystemExit(3)"],
        "env": {},
    }
    result = run_quality_gate_command(spec, project_root=tmp_path)
    assert result["ok"] is False
    assert result["returncode"] == 3
