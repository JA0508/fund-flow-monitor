from __future__ import annotations

import json

from tools.inspect_theme_regimes import inspect_theme_regimes, main


def test_inspect_theme_regimes_json_output(capsys) -> None:
    code = main(["--theme", "半导体/芯片链", "--source-mode", "SAMPLE", "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["source_mode"] == "SAMPLE"
    assert data["canonical_observation_basis"] == "canonical_bucket_observations"
    assert data["regime_signature_count"] >= 1
    assert data["regime_observation_examples"]


def test_inspect_theme_regimes_episodes_output(capsys) -> None:
    code = main(["--theme", "半导体/芯片链", "--source-mode", "SAMPLE", "--episodes", "--limit", "3"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Regime episodes" in out
    assert "observed timestamp span" in out


def test_inspect_theme_regimes_transitions_output(capsys) -> None:
    code = main(["--theme", "半导体/芯片链", "--source-mode", "SAMPLE", "--transitions"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Observed regime transition trace" in out
    assert "observed_transition_count" in out
    assert "probability" not in out.lower()


def test_inspect_theme_regimes_state_equivalent_output(capsys) -> None:
    evidence = inspect_theme_regimes("半导体/芯片链", source_mode="SAMPLE")
    state = evidence["latest_headline_state"]
    code = main(["--theme", "半导体/芯片链", "--source-mode", "SAMPLE", "--state-equivalent", "--headline-state", state])
    assert code == 0
    out = capsys.readouterr().out
    assert "State-equivalent structural analysis" in out
    assert "observed_signature_shares" in out
    assert "probability" not in out.lower()


def test_inspect_theme_regimes_unknown_theme(capsys) -> None:
    code = main(["--theme", "不存在主题", "--source-mode", "SAMPLE", "--json"])
    assert code == 1
    data = json.loads(capsys.readouterr().out)
    assert data["regime_available"] is False
    assert "未知主题" in data["warnings"][0]


def test_inspect_theme_regimes_missing_real_cache(tmp_path) -> None:
    evidence = inspect_theme_regimes("半导体/芯片链", source_mode="REAL", data_dir=str(tmp_path))
    assert evidence["regime_available"] is False
    assert evidence["canonical_observation_count"] == 0

