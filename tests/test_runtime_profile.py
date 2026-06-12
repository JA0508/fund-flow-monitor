from __future__ import annotations

from pathlib import Path

from src.runtime_profile import (
    build_runtime_profile_notice,
    build_runtime_profile_sidebar_defaults,
    detect_public_demo_profile,
    get_env_flag,
    get_runtime_profile,
    validate_runtime_profile_text,
)


def test_get_env_flag_true_values(monkeypatch):
    for value in ("1", "true", "yes", "y", "on", "TRUE"):
        monkeypatch.setenv("FLAG_TEST", value)
        assert get_env_flag("FLAG_TEST") is True


def test_get_env_flag_false_values(monkeypatch):
    for value in ("0", "false", "no", "n", "off", "FALSE"):
        monkeypatch.setenv("FLAG_TEST", value)
        assert get_env_flag("FLAG_TEST", default=True) is False


def test_get_env_flag_default(monkeypatch):
    monkeypatch.delenv("FLAG_TEST", raising=False)
    assert get_env_flag("FLAG_TEST", default=True) is True


def test_detect_public_demo_profile_default_off(monkeypatch):
    monkeypatch.delenv("FUND_FLOW_PUBLIC_DEMO", raising=False)
    monkeypatch.delenv("STREAMLIT_PUBLIC_DEMO", raising=False)
    profile = detect_public_demo_profile()
    assert profile["public_demo_enabled"] is False


def test_detect_public_demo_profile_env_on(monkeypatch):
    monkeypatch.setenv("FUND_FLOW_PUBLIC_DEMO", "1")
    profile = detect_public_demo_profile()
    assert profile["public_demo_enabled"] is True


def test_get_runtime_profile_without_sample_warns(monkeypatch, tmp_path):
    monkeypatch.setenv("FUND_FLOW_PUBLIC_DEMO", "1")
    profile = get_runtime_profile(tmp_path)
    assert profile["sample_data_available"] is False
    assert profile["errors"]


def test_get_runtime_profile_detects_sample_data(monkeypatch, tmp_path):
    sample_dir = tmp_path / "sample_data/ticks"
    sample_dir.mkdir(parents=True)
    (sample_dir / "sector_flow_2026-01-01.csv").write_text("sector_name,main_net_inflow_billion,captured_time\nAI,1,09:30:00\n")
    monkeypatch.delenv("FUND_FLOW_PUBLIC_DEMO", raising=False)
    profile = get_runtime_profile(tmp_path)
    assert profile["sample_data_available"] is True


def test_public_demo_defaults_to_sample(monkeypatch, tmp_path):
    sample_dir = tmp_path / "sample_data/ticks"
    sample_dir.mkdir(parents=True)
    (sample_dir / "sample.csv").write_text("sector_name,main_net_inflow_billion,captured_time\nAI,1,09:30:00\n")
    monkeypatch.setenv("FUND_FLOW_PUBLIC_DEMO", "1")
    profile = get_runtime_profile(tmp_path)
    assert profile["default_data_source_mode"] == "SAMPLE"


def test_public_demo_defaults_to_portfolio_mode(monkeypatch, tmp_path):
    (tmp_path / "sample_data/ticks").mkdir(parents=True)
    (tmp_path / "sample_data/ticks/sample.csv").write_text("a\n1\n")
    monkeypatch.setenv("FUND_FLOW_PUBLIC_DEMO", "1")
    profile = get_runtime_profile(tmp_path)
    assert profile["default_presentation_mode"] == "作品集演示模式"


def test_public_demo_safe_write_mode(monkeypatch, tmp_path):
    (tmp_path / "sample_data/ticks").mkdir(parents=True)
    (tmp_path / "sample_data/ticks/sample.csv").write_text("a\n1\n")
    monkeypatch.setenv("FUND_FLOW_PUBLIC_DEMO", "1")
    profile = get_runtime_profile(tmp_path)
    assert profile["safe_write_mode"] == "read_only_demo"


def test_public_demo_notice_has_sample_boundary(monkeypatch, tmp_path):
    (tmp_path / "sample_data/ticks").mkdir(parents=True)
    (tmp_path / "sample_data/ticks/sample.csv").write_text("a\n1\n")
    monkeypatch.setenv("FUND_FLOW_PUBLIC_DEMO", "1")
    notice = build_runtime_profile_notice(get_runtime_profile(tmp_path))
    assert "SAMPLE" in notice
    assert "合成演示数据" in notice
    assert "不代表真实行情" in notice


def test_sidebar_defaults_disable_auto_write(monkeypatch, tmp_path):
    (tmp_path / "sample_data/ticks").mkdir(parents=True)
    (tmp_path / "sample_data/ticks/sample.csv").write_text("a\n1\n")
    monkeypatch.setenv("FUND_FLOW_PUBLIC_DEMO", "1")
    defaults = build_runtime_profile_sidebar_defaults(get_runtime_profile(tmp_path))
    assert defaults["disable_auto_write"] is True


def test_validate_runtime_profile_text_forbidden():
    assert "未来会涨" in validate_runtime_profile_text("未来会涨")


def test_normal_runtime_notice_has_no_forbidden(monkeypatch, tmp_path):
    monkeypatch.delenv("FUND_FLOW_PUBLIC_DEMO", raising=False)
    notice = build_runtime_profile_notice(get_runtime_profile(Path(tmp_path)))
    assert validate_runtime_profile_text(notice) == []
