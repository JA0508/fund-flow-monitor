from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.inspect_theme_dynamics import inspect_theme_dynamics, main


def test_inspect_theme_dynamics_json_output(capsys) -> None:
    code = main(["--theme", "半导体/芯片链", "--source-mode", "SAMPLE", "--json"])
    out = capsys.readouterr().out
    assert code == 0
    assert '"theme_name": "半导体/芯片链"' in out
    assert '"source_mode": "SAMPLE"' in out


def test_inspect_theme_dynamics_state_scope_member_output(capsys) -> None:
    code = main(
        [
            "--theme",
            "半导体/芯片链",
            "--source-mode",
            "SAMPLE",
            "--state-trace",
            "--scope-divergence",
            "--member-divergence",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "State transition trace" in out
    assert "Scope divergence" in out
    assert "Member structural divergence" in out
    assert "observed share" in out


def test_inspect_theme_dynamics_unknown_theme() -> None:
    evidence, cube = inspect_theme_dynamics("不存在主题", source_mode="SAMPLE")
    assert evidence["dynamics_available"] is False
    assert cube.empty
    assert any("未知主题" in item for item in evidence["warnings"])


def test_inspect_theme_dynamics_missing_real_cache(tmp_path) -> None:
    evidence, cube = inspect_theme_dynamics("半导体/芯片链", source_mode="REAL", data_dir=str(tmp_path))
    assert cube.empty
    assert evidence["dynamics_available"] is False
    assert evidence["source_mode"] == "REAL"


def test_inspect_theme_dynamics_temp_real_cache(tmp_path) -> None:
    frame = pd.DataFrame(
        [
            {
                "trade_date": "2026-01-01",
                "captured_time": "09:30:00",
                "sector_type": "行业资金流",
                "sector_name": "半导体",
                "main_net_inflow_billion": 40.0,
                "source": "REAL",
                "data_mode": "REAL",
            }
        ]
    )
    frame.to_csv(Path(tmp_path) / "sector_flow_2026-01-01.csv", index=False)
    evidence, cube = inspect_theme_dynamics("半导体/芯片链", source_mode="REAL", data_dir=str(tmp_path))
    assert not cube.empty
    assert evidence["dynamics_available"] is True
    assert evidence["source_mode"] == "REAL"

