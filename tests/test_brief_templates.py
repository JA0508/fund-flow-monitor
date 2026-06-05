from __future__ import annotations

from src.brief_templates import (
    PORTFOLIO_BRIEF_MODE,
    STANDARD_BRIEF_MODE,
    build_brief_compliance_report,
    build_brief_metadata,
    build_brief_template_config,
    generate_brief_filename,
    get_brief_template_modes,
    is_portfolio_brief_mode,
    normalize_brief_template_mode,
    render_brief_markdown_v2,
    validate_brief_markdown_structure,
    validate_brief_template_text,
)


def _sample_brief() -> dict:
    return {
        "brief_title": "养基宝主题资金流观察简报",
        "brief_subtitle": "2026-01-16 ｜ 演示样例 ｜ 严格代表口径",
        "executive_summary": "当前为演示样例数据，仅解释已保存的资金流状态。",
        "key_points": ["主题雷达：偏强主题 2 个，承压主题 1 个。", "持仓相关池：关注组合相关主题分化。"],
        "risk_notes": ["主题口径存在上下级和交叉映射风险。"],
        "data_notes": ["数据日期：2026-01-16，最新时间：14:30:00。"],
        "disclaimer": "本简报仅用于学习研究和可视化观察，不构成投资建议，不预测未来走势。",
    }


def test_get_brief_template_modes_returns_two_modes():
    assert get_brief_template_modes() == [STANDARD_BRIEF_MODE, PORTFOLIO_BRIEF_MODE]


def test_normalize_brief_template_mode_defaults_to_standard():
    assert normalize_brief_template_mode(None) == STANDARD_BRIEF_MODE
    assert normalize_brief_template_mode("unknown") == STANDARD_BRIEF_MODE


def test_is_portfolio_brief_mode():
    assert is_portfolio_brief_mode(PORTFOLIO_BRIEF_MODE)
    assert not is_portfolio_brief_mode(STANDARD_BRIEF_MODE)


def test_build_brief_template_config_fields():
    config = build_brief_template_config(PORTFOLIO_BRIEF_MODE)
    assert config["mode"] == PORTFOLIO_BRIEF_MODE
    assert config["include_demo_notice"] is True
    assert "section_order" in config


def test_build_brief_metadata_sample_and_demo_not_real():
    sample = build_brief_metadata("2026-01-16", "SAMPLE")
    demo = build_brief_metadata("2026-01-16", "DEMO")
    assert sample["is_real_market_data"] is False
    assert "不代表真实行情" in sample["data_notice"]
    assert demo["is_real_market_data"] is False
    assert "不代表真实行情" in demo["data_notice"]


def test_build_brief_metadata_real_statuses():
    for status in ("LIVE", "CACHE", "HISTORY"):
        metadata = build_brief_metadata("2026-01-16", status)
        assert metadata["is_real_market_data"] is True
        assert metadata["data_notice"]


def test_render_brief_markdown_v2_has_sections():
    metadata = build_brief_metadata("2026-01-16", "SAMPLE", "严格代表口径")
    text = render_brief_markdown_v2(_sample_brief(), STANDARD_BRIEF_MODE, metadata)
    assert "# 养基宝主题资金流观察简报" in text
    assert "## 一、摘要" in text
    assert "## 二、关键观察" in text
    assert "## 六、免责声明" in text


def test_portfolio_brief_contains_project_section():
    metadata = build_brief_metadata("2026-01-16", "SAMPLE", "严格代表口径")
    text = render_brief_markdown_v2(_sample_brief(), PORTFOLIO_BRIEF_MODE, metadata)
    assert "## 七、项目展示说明" in text
    assert "合成演示数据" in text


def test_build_brief_compliance_report_detects_forbidden_word():
    report = build_brief_compliance_report("建议买入")
    assert report["forbidden_hits"]
    assert report["compliance_label"] == "存在禁词风险"


def test_validate_brief_markdown_structure_detects_missing_sections():
    report = validate_brief_markdown_structure("# 养基宝主题资金流观察简报")
    assert not report["is_valid"]
    assert report["warning_count"] > 0


def test_generate_brief_filename():
    assert generate_brief_filename("2026-01-16") == "yangjibao_brief_2026-01-16.md"
    assert generate_brief_filename("2026-01-16", PORTFOLIO_BRIEF_MODE) == "yangjibao_demo_brief_2026-01-16.md"


def test_validate_brief_template_text_detects_action_words():
    assert "建议买" in validate_brief_template_text("建议买入")


def test_normal_brief_template_text_has_no_forbidden_hits():
    metadata = build_brief_metadata("2026-01-16", "SAMPLE", "严格代表口径")
    text = render_brief_markdown_v2(_sample_brief(), PORTFOLIO_BRIEF_MODE, metadata)
    assert validate_brief_template_text(text) == []
