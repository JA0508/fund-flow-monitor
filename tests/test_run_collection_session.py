from __future__ import annotations

import argparse
import importlib.util
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tools import run_collection_session


def _args(**overrides) -> argparse.Namespace:
    values = {
        "max_runs": 3,
        "interval_seconds": 0,
        "respect_session": False,
        "dry_run": True,
        "no_network": False,
        "no_log": True,
        "stop_on_success": False,
        "stop_on_contract_error": False,
        "output_dir": "data/ticks",
        "log_path": "data/logs/collector_runs.jsonl",
        "sector_type": "行业资金流",
        "fetch_attempts": 1,
        "force": False,
        "quiet": True,
        "json": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _now():
    return datetime(2026, 6, 1, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_script_can_be_imported():
    path = Path("tools/run_collection_session.py")
    spec = importlib.util.spec_from_file_location("run_collection_session_cli", path)
    assert spec is not None and spec.loader is not None


def test_parser_accepts_expected_flags():
    parser = run_collection_session.build_parser()
    args = parser.parse_args(
        [
            "--max-runs",
            "2",
            "--interval-seconds",
            "0",
            "--dry-run",
            "--no-log",
            "--ignore-session",
            "--stop-on-success",
        ]
    )
    assert args.max_runs == 2
    assert args.interval_seconds == 0
    assert args.dry_run is True
    assert args.no_log is True
    assert args.respect_session is False
    assert args.stop_on_success is True


def test_runner_uses_finite_max_runs_and_fake_collector():
    calls = []

    def fake_collector(args):
        calls.append(args)
        return {"status": "dry_run", "row_count": 10, "written_rows": 0, "message": "dry"}

    summary = run_collection_session.run_collection_session(
        _args(max_runs=3, stop_on_success=False),
        collector_fn=fake_collector,
        sleep_fn=lambda seconds: None,
        now_fn=_now,
    )
    assert summary["attempted_runs"] == 3
    assert len(calls) == 3
    assert summary["dry_run_count"] == 3
    assert summary["final_status"] == "dry_run_completed"
    assert all(call.no_log for call in calls)


def test_runner_stop_on_success_stops_after_first_dry_run():
    def fake_collector(args):
        return {"status": "dry_run", "row_count": 10, "written_rows": 0, "message": "dry"}

    summary = run_collection_session.run_collection_session(
        _args(max_runs=5, stop_on_success=True),
        collector_fn=fake_collector,
        sleep_fn=lambda seconds: None,
        now_fn=_now,
    )
    assert summary["attempted_runs"] == 1
    assert summary["final_status"] == "dry_run_completed"


def test_runner_stop_on_contract_error():
    def fake_collector(args):
        return {"status": "contract_error", "error_category": "contract_error", "row_count": 0, "message": "contract"}

    summary = run_collection_session.run_collection_session(
        _args(max_runs=5, stop_on_contract_error=True),
        collector_fn=fake_collector,
        sleep_fn=lambda seconds: None,
        now_fn=_now,
    )
    assert summary["attempted_runs"] == 1
    assert summary["failure_count"] == 1
    assert summary["final_status"] == "completed_with_failures"


def test_runner_respect_session_blocks_outside_window(tmp_path):
    def fake_collector(args):
        raise AssertionError("collector should not run")

    outside = lambda: datetime(2026, 6, 1, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    summary = run_collection_session.run_collection_session(
        _args(respect_session=True, log_path=str(tmp_path / "missing.jsonl")),
        collector_fn=fake_collector,
        sleep_fn=lambda seconds: None,
        now_fn=outside,
    )
    assert summary["attempted_runs"] == 0
    assert summary["final_status"] == "blocked_by_policy"
    assert summary["policy_status"] == "outside_session"


def test_collector_args_do_not_force_real_write_when_dry_run():
    captured = {}

    def fake_collector(args):
        captured["args"] = args
        return {"status": "dry_run", "row_count": 1, "written_rows": 0, "message": "dry"}

    run_collection_session.run_collection_session(
        _args(dry_run=True, no_log=True),
        collector_fn=fake_collector,
        sleep_fn=lambda seconds: None,
        now_fn=_now,
    )
    assert captured["args"].dry_run is True
    assert captured["args"].no_log is True
    assert captured["args"].output_dir == "data/ticks"
