from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_quality_gate_commands(python_executable: str | None = None) -> list[dict]:
    python = python_executable or sys.executable
    return [
        {
            "name": "pytest",
            "label": "Unit tests",
            "command": [python, "-m", "pytest", "-q"],
            "env": {},
        },
        {
            "name": "compileall",
            "label": "Python compile check",
            "command": [python, "-m", "compileall", "app.py", "src", "tests", "tools"],
            "env": {},
        },
        {
            "name": "release_check",
            "label": "Release readiness",
            "command": [python, "tools/release_check.py"],
            "env": {},
        },
        {
            "name": "cloud_preflight",
            "label": "Cloud preflight",
            "command": [python, "tools/cloud_preflight.py"],
            "env": {},
        },
        {
            "name": "public_demo_preflight",
            "label": "Public demo preflight",
            "command": [python, "tools/cloud_preflight.py"],
            "env": {"FUND_FLOW_PUBLIC_DEMO": "1"},
        },
        {
            "name": "smoke_check",
            "label": "Smoke check",
            "command": [python, "tools/smoke_check.py"],
            "env": {},
        },
        {
            "name": "verify_runtime",
            "label": "Runtime verification",
            "command": [python, "tools/verify_runtime.py"],
            "env": {},
        },
    ]


def filter_quality_gate_commands(
    commands: list[dict],
    only: Iterable[str] | None = None,
    skip: Iterable[str] | None = None,
) -> list[dict]:
    only_set = {item for item in (only or []) if item}
    skip_set = {item for item in (skip or []) if item}
    filtered = []
    for command in commands:
        name = command["name"]
        if only_set and name not in only_set:
            continue
        if name in skip_set:
            continue
        filtered.append(command)
    return filtered


def run_quality_gate_command(command_spec: dict, project_root: str | Path = PROJECT_ROOT) -> dict:
    start = time.perf_counter()
    env = os.environ.copy()
    env.update(command_spec.get("env", {}))
    result = subprocess.run(
        command_spec["command"],
        cwd=project_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - start
    return {
        "name": command_spec["name"],
        "label": command_spec.get("label", command_spec["name"]),
        "command": command_spec["command"],
        "env": command_spec.get("env", {}),
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "elapsed_seconds": round(elapsed, 2),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_quality_gate(
    project_root: str | Path = PROJECT_ROOT,
    python_executable: str | None = None,
    only: Iterable[str] | None = None,
    skip: Iterable[str] | None = None,
    stop_on_failure: bool = False,
    quiet: bool = False,
    verbose: bool = False,
) -> dict:
    commands = filter_quality_gate_commands(
        build_quality_gate_commands(python_executable),
        only=only,
        skip=skip,
    )
    results = []
    if not quiet:
        print("Quality gate")
        print(f"  project_root: {Path(project_root).resolve()}")
        print(f"  check_count: {len(commands)}")
    for command in commands:
        if not quiet:
            print(f"  running: {command['name']} - {command.get('label', command['name'])}")
        result = run_quality_gate_command(command, project_root=project_root)
        results.append(result)
        if not quiet:
            status = "PASS" if result["ok"] else "FAIL"
            print(f"    {status} ({result['elapsed_seconds']}s)")
        if verbose or (not result["ok"] and not quiet):
            stdout = result.get("stdout", "").strip()
            stderr = result.get("stderr", "").strip()
            if stdout:
                print(stdout)
            if stderr:
                print(stderr, file=sys.stderr)
        if stop_on_failure and not result["ok"]:
            break

    failed = [item["name"] for item in results if not item["ok"]]
    report = {
        "quality_gate_ok": not failed,
        "check_count": len(results),
        "failed_checks": failed,
        "results": results,
        "exit_code": 0 if not failed else 1,
    }
    if not quiet:
        print(f"  quality_gate_ok: {report['quality_gate_ok']}")
        print(f"  failed_checks: {failed}")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local pre-push quality gate.")
    parser.add_argument("--list", action="store_true", help="List available checks without running them.")
    parser.add_argument("--only", nargs="*", default=None, help="Run only the named checks.")
    parser.add_argument("--skip", nargs="*", default=None, help="Skip the named checks.")
    parser.add_argument("--stop-on-failure", action="store_true", help="Stop after the first failed check.")
    parser.add_argument("--quiet", action="store_true", help="Print only minimal output.")
    parser.add_argument("--verbose", action="store_true", help="Print stdout/stderr for every check.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    commands = build_quality_gate_commands()
    if args.list:
        for command in commands:
            env_prefix = " ".join(f"{key}={value}" for key, value in command.get("env", {}).items())
            command_text = " ".join(command["command"])
            print(f"{command['name']}: {env_prefix + ' ' if env_prefix else ''}{command_text}")
        return 0
    report = run_quality_gate(
        only=args.only,
        skip=args.skip,
        stop_on_failure=args.stop_on_failure,
        quiet=args.quiet,
        verbose=args.verbose,
    )
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
