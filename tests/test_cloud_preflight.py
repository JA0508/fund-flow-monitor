from __future__ import annotations

from pathlib import Path

from tools.cloud_preflight import (
    build_cloud_preflight_report,
    build_parser,
    run_cloud_preflight,
)


def _create_minimal_public_demo_project(root: Path) -> None:
    (root / ".streamlit").mkdir(parents=True)
    (root / "sample_data/ticks").mkdir(parents=True)
    (root / "docs/demo_briefs").mkdir(parents=True)
    (root / "docs/screenshots").mkdir(parents=True)
    (root / "tools").mkdir(parents=True)
    (root / "src").mkdir(parents=True)
    (root / "app.py").write_text("print('app')\n")
    (root / "requirements.txt").write_text("streamlit\npandas\n")
    (root / ".streamlit/config.toml").write_text("[theme]\nbase='dark'\n")
    (root / ".streamlit/secrets.example.toml").write_text("# example only\n")
    (root / "sample_data/ticks/sector_flow_2026-01-01.csv").write_text(
        "captured_time,sector_type,sector_name,main_net_inflow_billion,source,data_mode\n"
        "09:30:00,行业资金流,AI,1,SAMPLE,SAMPLE\n"
    )
    (root / "docs/demo_briefs/sample_observation_brief.md").write_text(
        "SAMPLE 合成演示数据，不代表真实行情，不构成投资建议，不预测未来走势。\n"
    )
    (root / "docs/ARCHITECTURE.md").write_text("SAMPLE 合成演示数据架构说明。\n")
    (root / "docs/DATA_FLOW.md").write_text("SAMPLE 合成演示数据流说明。\n")
    (root / "docs/OPERATIONS.md").write_text("SAMPLE 合成演示数据运维说明。\n")
    (root / "docs/screenshots/01_home_sample_status.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (root / "README.md").write_text(
        "SAMPLE 合成演示数据，不代表真实行情，不构成投资建议，不预测未来走势。\n"
        "[Demo](docs/demo_briefs/sample_observation_brief.md)\n"
    )
    (root / "tools/release_check.py").write_text("print('release')\n")
    (root / "tools/quality_gate.py").write_text("print('quality')\n")
    (root / "src/runtime_profile.py").write_text("# placeholder\n")
    (root / "src/data_contracts.py").write_text("# placeholder\n")
    (root / ".gitignore").write_text(
        "data/ticks/*.csv\n"
        "data/warehouse/\n"
        "*.sqlite\n"
        "*.sqlite3\n"
        "*.db\n"
        ".env\n"
        ".venv/\n"
        ".streamlit/secrets.toml\n"
        "__pycache__/\n"
        ".pytest_cache/\n"
    )


def test_cloud_preflight_script_parser_exists():
    parser = build_parser()
    args = parser.parse_args(["--strict", "--public-demo-env", "--quiet"])
    assert args.strict is True
    assert args.public_demo_env is True


def test_cloud_preflight_missing_assets(tmp_path):
    report = build_cloud_preflight_report(tmp_path)
    assert report["error_count"] > 0
    assert report["missing_assets"]


def test_cloud_preflight_minimal_assets(tmp_path, monkeypatch):
    _create_minimal_public_demo_project(tmp_path)
    monkeypatch.setenv("FUND_FLOW_PUBLIC_DEMO", "1")
    report = build_cloud_preflight_report(tmp_path, public_demo_env=True)
    assert report["sample_data_available"] is True
    assert report["demo_brief_available"] is True
    assert report["public_demo_default_source"] == "SAMPLE"


def test_cloud_preflight_first_visit_without_local_cache_uses_sample(tmp_path, monkeypatch):
    _create_minimal_public_demo_project(tmp_path)
    monkeypatch.delenv("FUND_FLOW_PUBLIC_DEMO", raising=False)
    report = build_cloud_preflight_report(tmp_path, public_demo_env=False)
    assert report["sample_data_available"] is True
    assert report["public_demo_default_source"] == "SAMPLE"


def test_cloud_preflight_strict_exit_code_for_errors(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    report = build_cloud_preflight_report(tmp_path)
    report["exit_code"] = 1 if report["error_count"] else 0
    assert report["exit_code"] == 1


def test_run_cloud_preflight_default_project_quiet():
    report = run_cloud_preflight(strict=False, quiet=True, public_demo_env=False)
    assert "cloud_readiness_label" in report


def test_cloud_preflight_does_not_create_warehouse(tmp_path):
    _create_minimal_public_demo_project(tmp_path)
    build_cloud_preflight_report(tmp_path, public_demo_env=True)
    assert not (tmp_path / "data/warehouse").exists()


def test_cloud_preflight_does_not_write_data_ticks(tmp_path):
    _create_minimal_public_demo_project(tmp_path)
    before = sorted((tmp_path / "data").glob("ticks/*.csv")) if (tmp_path / "data").exists() else []
    build_cloud_preflight_report(tmp_path, public_demo_env=True)
    after = sorted((tmp_path / "data").glob("ticks/*.csv")) if (tmp_path / "data").exists() else []
    assert before == after


def test_cloud_preflight_output_no_forbidden(tmp_path, monkeypatch):
    _create_minimal_public_demo_project(tmp_path)
    monkeypatch.setenv("FUND_FLOW_PUBLIC_DEMO", "1")
    report = build_cloud_preflight_report(tmp_path, public_demo_env=True)
    assert report["forbidden_hits"] == []
