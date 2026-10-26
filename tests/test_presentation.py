from __future__ import annotations

from pathlib import Path

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
    sync_brief_theme_from_radar,
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


def test_sync_brief_theme_from_radar_updates_only_until_brief_has_a_manual_choice():
    state = {
        "theme_radar_evidence_theme": "半导体/芯片链",
        "brief_provenance_theme": "新能源链",
    }

    sync_brief_theme_from_radar(state)

    assert state["brief_provenance_theme"] == "半导体/芯片链"
    assert state["brief_provenance_theme_user_selected"] is False

    state["brief_provenance_theme"] = "医药主题"
    state["brief_provenance_theme_user_selected"] = True
    state["theme_radar_evidence_theme"] = "红利防御"

    sync_brief_theme_from_radar(state)

    assert state["brief_provenance_theme"] == "医药主题"


def test_theme_radar_places_selected_theme_evidence_before_market_overview():
    app_source = Path(__file__).parents[1].joinpath("app.py").read_text(encoding="utf-8")
    radar_body = app_source.split("    with tab_radar:", maxsplit=1)[1].split("    with tab_intraday:", maxsplit=1)[0]
    assert radar_body.index('key="theme_radar_evidence_theme"') < radar_body.index("render_market_temperature_card")
    assert radar_body.index("render_theme_observation_evidence_cards(evidence)") < radar_body.index("render_theme_radar_cards")


def test_live_curve_keeps_one_complete_sample_status_explanation():
    app_source = Path(__file__).parents[1].joinpath("app.py").read_text(encoding="utf-8")
    curve_body = app_source.split("    with tab_curve:", maxsplit=1)[1].split("    with tab_radar:", maxsplit=1)[0]
    assert "render_status_badge(status_badge_config)" not in curve_body
    assert "render_status_bar(" in curve_body
    assert 'data_source_label="SAMPLE synthetic CSV" if sample_mode else None' in curve_body
    assert 'extra_status = f"数据来源：{source_label}"' not in app_source
    assert 'extra_status = f"主题口径：{theme_mode_label}"' in app_source


def test_sidebar_hides_multi_day_settings_until_requested():
    app_source = Path(__file__).parents[1].joinpath("app.py").read_text(encoding="utf-8")
    sidebar_body = app_source.split("    with st.sidebar:", maxsplit=1)[1].split("    st_autorefresh", maxsplit=1)[0]
    assert 'with st.expander("多日趋势设置", expanded=False):' in sidebar_body
    assert sidebar_body.index('with st.expander("多日趋势设置", expanded=False):') < sidebar_body.index('key="multi_day_trend_mode_label"')


def test_brief_defaults_to_the_theme_currently_selected_on_the_radar():
    app_source = Path(__file__).parents[1].joinpath("app.py").read_text(encoding="utf-8")
    brief_body = app_source.split("    with tab_brief:", maxsplit=1)[1].split("    with tab_rank:", maxsplit=1)[0]
    assert 'st.session_state.get("theme_radar_evidence_theme")' in brief_body
    assert "brief_theme_index = (" in brief_body
    assert "index=brief_theme_index" in brief_body


def test_brief_keeps_optional_warehouse_history_out_of_the_primary_theme_selection_path():
    app_source = Path(__file__).parents[1].joinpath("app.py").read_text(encoding="utf-8")
    brief_body = app_source.split("    with tab_brief:", maxsplit=1)[1].split("    with tab_rank:", maxsplit=1)[0]
    assert 'with st.expander("可选：本地 Warehouse 历史摘要", expanded=False):' in brief_body
    assert brief_body.index('key="brief_provenance_theme"') < brief_body.index(
        'with st.expander("可选：本地 Warehouse 历史摘要", expanded=False):'
    )
    assert 'value=False,' in brief_body[brief_body.index('key="brief_include_theme_history"') - 300 : brief_body.index('key="brief_include_theme_history"')]
