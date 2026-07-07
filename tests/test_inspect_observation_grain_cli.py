from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.inspect_observation_grain import build_observation_grain_report, main


def _write_snapshot(path: Path, trade_date: str, rows: list[dict]) -> None:
    frame = pd.DataFrame(rows)
    frame["trade_date"] = trade_date
    frame["sector_type"] = "行业资金流"
    frame["source"] = frame.get("source", "SAMPLE")
    frame["data_mode"] = frame.get("data_mode", "SAMPLE")
    frame.to_csv(path / f"sector_flow_{trade_date}.csv", index=False)


def _rows(time_value: str, semi: float) -> list[dict]:
    return [
        {"captured_time": time_value, "sector_name": "半导体", "main_net_inflow_billion": semi},
        {"captured_time": time_value, "sector_name": "电子", "main_net_inflow_billion": 1.0},
        {"captured_time": time_value, "sector_name": "计算机", "main_net_inflow_billion": -3.0},
    ]


def test_observation_grain_json_output(capsys) -> None:
    code = main(["--source-mode", "SAMPLE", "--theme", "半导体/芯片链", "--json"])
    out = capsys.readouterr().out
    assert code == 0
    assert '"source_mode": "SAMPLE"' in out
    assert '"raw_event_grain"' in out
    assert '"bucketed_analytical_grain"' in out
    assert '"materialization_policy"' in out


def test_observation_grain_collision_and_canonical_output(tmp_path, capsys) -> None:
    _write_snapshot(tmp_path, "2026-01-01", _rows("09:30:00", 30.0) + _rows("09:30:40", 35.0))
    code = main(
        [
            "--source-mode",
            "SAMPLE",
            "--data-dir",
            str(tmp_path),
            "--theme",
            "半导体/芯片链",
            "--collisions",
            "--canonical",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "Observation grain audit" in out
    assert "collided buckets" in out
    assert "Canonical observation examples" in out
    assert "multiple_events_same_bucket" in out


def test_observation_grain_report_missing_real_cache(tmp_path) -> None:
    report = build_observation_grain_report(source_mode="REAL", data_dir=str(tmp_path), theme="半导体/芯片链")
    assert report["source_mode"] == "REAL"
    assert report["grain_available"] is False
    assert report["raw_event_count"] == 0
    assert report["canonical_observation_count"] == 0


def test_observation_grain_report_filters_theme_and_date(tmp_path) -> None:
    _write_snapshot(tmp_path, "2026-01-01", _rows("09:30:00", 30.0))
    _write_snapshot(tmp_path, "2026-01-02", _rows("09:30:00", -30.0))
    report = build_observation_grain_report(
        source_mode="SAMPLE",
        data_dir=str(tmp_path),
        theme="半导体/芯片链",
        date="2026-01-02",
        mode="strict_representative",
    )
    assert report["raw_event_count"] == 1
    assert report["canonical_observation_count"] == 1
    assert report["canonical_examples"][0]["trade_date"] == "2026-01-02"
