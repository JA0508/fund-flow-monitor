from __future__ import annotations

from src.theme_history_brief import (
    build_theme_history_brief_compliance_report,
    build_theme_history_brief_context,
    build_theme_history_brief_points,
    build_theme_history_brief_risk_notes,
    merge_theme_history_section_into_markdown,
    render_theme_history_brief_section,
    validate_theme_history_brief_text,
)


def _sample_summary() -> dict:
    return {
        "history_available": True,
        "date_count": 2,
        "theme_count": 8,
        "latest_date": "2026-01-16",
        "strongest_latest_themes": ["AI算力/TMT", "半导体/芯片链"],
        "pressured_latest_themes": ["新能源链", "医药"],
        "most_consistent_positive_themes": ["AI算力/TMT"],
        "most_consistent_pressure_themes": ["新能源链"],
        "high_variation_themes": ["红利防御"],
        "summary_label": "仅 SAMPLE 主题历史可用",
        "summary_reason": "当前 warehouse 中仅包含 SAMPLE 合成演示数据，可用于展示主题历史聚合流程，不代表真实行情。",
        "warnings": [],
        "errors": [],
    }


def test_build_theme_history_brief_context_empty():
    context = build_theme_history_brief_context(None)
    assert context["history_brief_available"] is False
    assert "暂无" in context["summary_label"]


def test_build_theme_history_brief_context_sample_notice():
    context = build_theme_history_brief_context(_sample_summary(), source_type="SAMPLE", theme_mode="代表口径")
    assert context["history_brief_available"] is True
    assert "合成演示数据" in context["data_notice"]
    assert "不代表真实行情" in context["data_notice"]


def test_build_theme_history_brief_context_local_no_sample_notice():
    summary = _sample_summary()
    summary["summary_reason"] = "当前 warehouse 中存在多个历史日期，可用于只读观察主题资金状态变化。"
    context = build_theme_history_brief_context(summary, source_type="LOCAL", theme_mode="代表口径")
    assert "SAMPLE" not in context["data_notice"]
    assert "LOCAL" in context["data_notice"]


def test_build_theme_history_brief_points_safe():
    context = build_theme_history_brief_context(_sample_summary(), source_type="SAMPLE", theme_mode="代表口径")
    points = build_theme_history_brief_points(context)
    assert points
    assert validate_theme_history_brief_text("\n".join(points)) == []


def test_build_theme_history_brief_risk_notes_include_boundaries():
    context = build_theme_history_brief_context(_sample_summary(), source_type="SAMPLE", theme_mode="代表口径")
    notes = build_theme_history_brief_risk_notes(context)
    text = "\n".join(notes)
    assert "source of truth" in text
    assert "不预测未来走势" in text
    assert "不构成投资建议" in text


def test_render_theme_history_brief_section_outputs_heading():
    context = build_theme_history_brief_context(_sample_summary(), source_type="SAMPLE", theme_mode="代表口径")
    section = render_theme_history_brief_section(context)
    assert "## 主题历史观察摘要" in section
    assert "合成演示数据" in section
    assert "不构成投资建议" in section


def test_render_theme_history_brief_section_unavailable():
    context = build_theme_history_brief_context(None)
    section = render_theme_history_brief_section(context)
    assert "暂无可用 warehouse 主题历史摘要" in section
    assert "source of truth" in section


def test_merge_theme_history_section_into_markdown_after_heading():
    markdown = "# A\n\n## 三、主题与持仓相关观察\n\n- old\n\n## 四、口径与数据说明\n\n- data\n"
    merged = merge_theme_history_section_into_markdown(markdown, "## 主题历史观察摘要\n\n- new")
    assert merged.index("## 主题历史观察摘要") < merged.index("## 四、口径与数据说明")


def test_merge_theme_history_section_into_markdown_fallback():
    markdown = "# A\n\n## 六、免责声明\n\nx\n"
    merged = merge_theme_history_section_into_markdown(markdown, "## 主题历史观察摘要\n\n- new")
    assert merged.index("## 主题历史观察摘要") < merged.index("## 六、免责声明")


def test_compliance_report_detects_forbidden():
    report = build_theme_history_brief_compliance_report("未来会涨，建议关注")
    assert report["compliance_label"] == "存在禁词风险"
    assert "未来会涨" in report["forbidden_hits"]
    assert "建议关注" in report["forbidden_hits"]


def test_compliance_report_checks_required_notices():
    context = build_theme_history_brief_context(_sample_summary(), source_type="SAMPLE", theme_mode="代表口径")
    section = render_theme_history_brief_section(context)
    report = build_theme_history_brief_compliance_report(section)
    assert report["compliance_label"] == "合规通过"
    assert report["has_sample_notice"] is True
    assert report["has_no_prediction_notice"] is True
    assert report["has_no_advice_notice"] is True
    assert report["has_source_of_truth_notice"] is True


def test_validate_theme_history_brief_text_detects_forbidden():
    hits = validate_theme_history_brief_text("趋势确立，反转确认，强烈看好，明确机会")
    assert "趋势确立" in hits
    assert "反转确认" in hits
    assert "强烈看好" in hits
    assert "明确机会" in hits


def test_normal_section_has_no_advice_or_prediction_words():
    context = build_theme_history_brief_context(_sample_summary(), source_type="SAMPLE", theme_mode="代表口径")
    section = render_theme_history_brief_section(context)
    assert validate_theme_history_brief_text(section) == []
