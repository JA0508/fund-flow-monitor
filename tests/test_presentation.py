from __future__ import annotations

from src.presentation import (
    PORTFOLIO_MODE,
    STANDARD_MODE,
    build_demo_walkthrough_steps,
    build_portfolio_intro_context,
    build_screenshot_checklist,
    build_status_badge_config,
    get_display_mode_options,
    is_portfolio_mode,
    normalize_display_mode,
    should_show_debug_details,
    validate_presentation_text,
)


def test_get_display_mode_options_returns_two_modes():
    assert get_display_mode_options() == [STANDARD_MODE, PORTFOLIO_MODE]


def test_normalize_display_mode_empty_returns_standard():
    assert normalize_display_mode(None) == STANDARD_MODE


def test_normalize_display_mode_unknown_returns_standard():
    assert normalize_display_mode("unknown") == STANDARD_MODE


def test_is_portfolio_mode_recognizes_portfolio_mode():
    assert is_portfolio_mode(PORTFOLIO_MODE)
    assert not is_portfolio_mode(STANDARD_MODE)


def test_should_show_debug_details_standard_mode_true():
    assert should_show_debug_details(STANDARD_MODE)


def test_should_show_debug_details_portfolio_mode_false():
    assert not should_show_debug_details(PORTFOLIO_MODE)


def test_build_status_badge_config_live():
    badge = build_status_badge_config("LIVE")
    assert badge["short_label"] == "LIVE"
    assert badge["is_real_market_data"] is True


def test_build_status_badge_config_sample_not_real_market_data():
    badge = build_status_badge_config("SAMPLE")
    assert badge["short_label"] == "SAMPLE"
    assert badge["is_real_market_data"] is False
    assert badge["is_demo_like"] is True


def test_build_status_badge_config_demo_not_real_market_data():
    badge = build_status_badge_config("DEMO")
    assert badge["short_label"] == "DEMO"
    assert badge["is_real_market_data"] is False


def test_build_status_badge_config_empty():
    badge = build_status_badge_config("EMPTY")
    assert badge["short_label"] == "EMPTY"
    assert badge["tone"] == "danger"


def test_build_portfolio_intro_context_outputs_capabilities_and_boundaries():
    context = build_portfolio_intro_context("v1.8", "SAMPLE", "2026-01-16", PORTFOLIO_MODE)
    assert context["key_capabilities"]
    assert context["boundary_notes"]
    assert context["status_badge"]["short_label"] == "SAMPLE"


def test_build_screenshot_checklist_outputs_at_least_six_items():
    checklist = build_screenshot_checklist()
    assert len(checklist) >= 6
    assert {"screenshot_name", "target_tab", "recommended_mode"}.issubset(checklist[0])


def test_build_demo_walkthrough_steps_outputs_steps():
    steps = build_demo_walkthrough_steps()
    assert steps
    assert {"step_title", "target_tab", "description"}.issubset(steps[0])


def test_validate_presentation_text_detects_forbidden_words():
    hits = validate_presentation_text("这里出现买入和未来会涨")
    assert "买入" in hits
    assert "未来会涨" in hits


def test_normal_presentation_copy_has_no_forbidden_words():
    context = build_portfolio_intro_context("v1.8", "CACHE", "2026-06-03", PORTFOLIO_MODE)
    text = " ".join(
        [
            context["title"],
            context["subtitle"],
            context["value_proposition"],
            " ".join(context["key_capabilities"]),
            " ".join(context["boundary_notes"]),
        ]
    )
    assert validate_presentation_text(text) == []
