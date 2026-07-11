from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.providers.akshare_sector_flow import normalize_provider_dataframe
from tools.audit_evidence_accumulation import build_parser


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _raw_provider_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "序号": [1],
            "板块代码": ["BK001"],
            "名称": ["半导体"],
            "今日涨跌幅": [1.2],
            "今日主力净流入-净额": [100_000_000],
            "今日主力净流入-净占比": [3.2],
            "今日超大单净流入-净额": [50_000_000],
            "今日大单净流入-净额": [30_000_000],
            "今日中单净流入-净额": [10_000_000],
            "今日小单净流入-净额": [10_000_000],
            "今日主力净流入最大股": ["样例A"],
            "今日主力净流入最大股代码": ["000001"],
        }
    )


def _write_snapshot(tmp_path, times: list[str]) -> None:
    frames = []
    for value in times:
        result = normalize_provider_dataframe(
            _raw_provider_frame(),
            sector_type="行业资金流",
            captured_at=datetime.fromisoformat(f"2026-06-10T{value}+08:00"),
        )
        frames.append(result.normalized_df)
    df = pd.concat(frames, ignore_index=True)
    (tmp_path / "sector_flow_2026-06-10.csv").write_text(df.to_csv(index=False), encoding="utf-8")


def test_parser_accepts_source_and_cell_minutes():
    args = build_parser().parse_args(["--source", "REAL", "--cell-minutes", "15", "--json"])
    assert args.source_mode == "REAL"
    assert args.cell_minutes == 15
    assert args.json is True


def test_cli_json_is_offline_and_reports_coverage(tmp_path):
    _write_snapshot(tmp_path, ["10:00:00", "10:05:00", "10:40:00"])
    result = subprocess.run(
        [
            sys.executable,
            "tools/audit_evidence_accumulation.py",
            "--source",
            "REAL",
            "--data-dir",
            str(tmp_path),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    report = json.loads(result.stdout)
    assert report["network_used"] is False
    assert report["physical_capture_event_count"] == 3
    assert report["qualified_capture_event_count"] == 3
    assert report["covered_acquisition_cell_count"] == 2
    assert report["calendar_unverified_capture_count"] == 0
    assert report["market_session_date_policy"]["source_classification"] == "provider_derived"
    assert report["market_session_date_policy"]["network_used"] is False


def test_cli_does_not_create_data_warehouse_or_ticks(tmp_path):
    _write_snapshot(tmp_path, ["10:00:00"])
    subprocess.run(
        [
            sys.executable,
            "tools/audit_evidence_accumulation.py",
            "--source",
            "REAL",
            "--data-dir",
            str(tmp_path),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert not (tmp_path / "data").exists()
    assert sorted(path.name for path in tmp_path.glob("*.csv")) == ["sector_flow_2026-06-10.csv"]
