from __future__ import annotations

from pathlib import Path

from src.release_readiness import (
    build_release_readiness_report,
    check_sample_data_contract,
    check_tracked_file_safety,
    check_gitignore_safety,
    check_required_public_assets,
    check_sample_notice_coverage,
    check_version_consistency,
    get_release_audit_targets,
    render_release_readiness_markdown,
    scan_markdown_links,
    scan_text_for_forbidden_investment_phrases,
    scan_text_for_local_paths,
    scan_text_for_sensitive_terms,
    validate_release_readiness_text,
)


def test_get_release_audit_targets_tmp_path_does_not_crash(tmp_path: Path):
    result = get_release_audit_targets(tmp_path)
    assert "missing_files" in result
    assert "missing_dirs" in result


def test_scan_text_for_local_paths_detects_users_path():
    assert scan_text_for_local_paths("/Users/test/project/file.py")


def test_scan_text_for_local_paths_plain_text_empty():
    assert scan_text_for_local_paths("SAMPLE 合成演示数据，不代表真实行情。") == []


def test_scan_text_for_local_paths_allows_streamlit_url():
    text = "https://fund-flow-monitor-ja0508.streamlit.app/"
    assert scan_text_for_local_paths(text) == []


def test_scan_text_for_sensitive_terms_detects_api_key_and_password():
    hits = scan_text_for_sensitive_terms("API key = abc\npassword = hidden")
    assert "API key" in hits
    assert "password" in hits


def test_scan_text_for_forbidden_investment_phrases_detects_risky_text():
    hits = scan_text_for_forbidden_investment_phrases("建议买，未来会涨")
    assert "建议买" in hits
    assert "未来会涨" in hits


def test_scan_markdown_links_existing_relative(tmp_path: Path):
    (tmp_path / "doc.md").write_text("ok", encoding="utf-8")
    result = scan_markdown_links("[doc](doc.md)", tmp_path)
    assert result["existing_links"] == ["doc.md"]
    assert result["missing_links"] == []


def test_scan_markdown_links_missing_relative(tmp_path: Path):
    result = scan_markdown_links("[missing](missing.md)", tmp_path)
    assert result["missing_links"] == ["missing.md"]


def test_check_required_public_assets_missing_assets(tmp_path: Path):
    result = check_required_public_assets(tmp_path)
    assert result["missing_assets"]
    assert result["error_count"] > 0


def test_check_sample_notice_coverage_detects_missing_notice(tmp_path: Path):
    for rel in ("README.md", "docs/demo_briefs/sample_observation_brief.md", "docs/screenshots/SCREENSHOT_GUIDE.md", "PROJECT_BRIEF.md"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("plain text", encoding="utf-8")
    result = check_sample_notice_coverage(tmp_path)
    assert result["missing_notice_files"]
    assert result["warning_count"] > 0


def test_check_gitignore_safety_detects_missing_sqlite_ignore(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("data/ticks/*.csv\n", encoding="utf-8")
    result = check_gitignore_safety(tmp_path)
    assert "*.sqlite" in result["required_patterns_missing"]
    assert result["error_count"] > 0


def test_check_sample_data_contract_detects_bad_sample_marker(tmp_path: Path):
    sample_dir = tmp_path / "sample_data/ticks"
    sample_dir.mkdir(parents=True)
    (sample_dir / "sector_flow_2026-01-15.csv").write_text(
        "captured_time,sector_type,sector_name,main_net_inflow_billion,source,data_mode\n"
        "09:35:00,行业资金流,半导体,1.2,LOCAL,LOCAL\n",
        encoding="utf-8",
    )
    result = check_sample_data_contract(tmp_path)
    assert result["error_count"] > 0
    assert result["contract_ok"] is False


def test_check_sample_data_contract_passes_valid_sample(tmp_path: Path):
    sample_dir = tmp_path / "sample_data/ticks"
    sample_dir.mkdir(parents=True)
    (sample_dir / "sector_flow_2026-01-15.csv").write_text(
        "captured_time,sector_type,sector_name,main_net_inflow_billion,source,data_mode\n"
        "09:35:00,行业资金流,半导体,1.2,SAMPLE,SAMPLE\n",
        encoding="utf-8",
    )
    result = check_sample_data_contract(tmp_path)
    assert result["contract_ok"] is True
    assert result["file_count"] == 1


def test_check_version_consistency_detects_missing_changelog_version(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/config.py").write_text('APP_VERSION = "v9.9"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# CHANGELOG\n\n## v1.0\n", encoding="utf-8")
    result = check_version_consistency(tmp_path)
    assert result["app_version"] == "v9.9"
    assert result["changelog_version_ok"] is False
    assert result["error_count"] > 0


def test_check_version_consistency_passes_when_changelog_has_version(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/config.py").write_text('APP_VERSION = "v9.9"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# CHANGELOG\n\n## v9.9\n", encoding="utf-8")
    result = check_version_consistency(tmp_path)
    assert result["changelog_version_ok"] is True
    assert result["error_count"] == 0


def test_check_tracked_file_safety_non_git_tmp_path_does_not_crash(tmp_path: Path):
    result = check_tracked_file_safety(tmp_path)
    assert "tracked_forbidden_files" in result
    assert result["error_count"] == 0


def test_build_release_readiness_report_returns_label(tmp_path: Path):
    result = build_release_readiness_report(tmp_path)
    assert result["readiness_label"]


def test_render_release_readiness_markdown_outputs_heading(tmp_path: Path):
    report = build_release_readiness_report(tmp_path)
    markdown = render_release_readiness_markdown(report)
    assert markdown.startswith("# Release Readiness Report")


def test_validate_release_readiness_text_detects_local_path():
    assert validate_release_readiness_text("请查看 /Users/test/project")


def test_normal_release_readiness_text_has_no_forbidden_hits():
    text = "SAMPLE 合成演示数据仅用于展示，不代表真实行情，不预测未来走势，不构成投资建议。"
    assert scan_text_for_forbidden_investment_phrases(text) == []
