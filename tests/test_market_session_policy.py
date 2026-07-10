from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.market_session_policy import (
    STATE_ELIGIBLE,
    STATE_INELIGIBLE,
    STATE_UNVERIFIED,
    build_declared_market_session_policy,
    evaluate_market_session_date,
    get_default_market_session_policy,
    validate_market_session_policy_text,
)


def test_default_policy_is_conservative_and_unverified():
    policy = get_default_market_session_policy()
    decision = evaluate_market_session_date("2026-06-01", policy)
    assert decision["is_market_session_date_eligible"] is False
    assert decision["market_session_date_state"] == STATE_UNVERIFIED
    assert decision["network_used"] is False


def test_declared_eligible_date_is_eligible():
    policy = build_declared_market_session_policy(
        eligible_dates=["2026-06-01"],
        coverage_start="2026-06-01",
        coverage_end="2026-06-05",
    )
    decision = evaluate_market_session_date(datetime(2026, 6, 1, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")), policy)
    assert decision["is_market_session_date_eligible"] is True
    assert decision["market_session_date_state"] == STATE_ELIGIBLE
    assert decision["calendar_coverage_state"] == "declared_calendar_coverage"


def test_date_inside_declared_range_but_not_eligible_is_ineligible():
    policy = build_declared_market_session_policy(
        eligible_dates=["2026-06-01"],
        coverage_start="2026-06-01",
        coverage_end="2026-06-05",
    )
    decision = evaluate_market_session_date("2026-06-02", policy)
    assert decision["is_market_session_date_eligible"] is False
    assert decision["market_session_date_state"] == STATE_INELIGIBLE


def test_date_outside_declared_range_is_unverified():
    policy = build_declared_market_session_policy(
        eligible_dates=["2026-06-01"],
        coverage_start="2026-06-01",
        coverage_end="2026-06-05",
    )
    decision = evaluate_market_session_date("2026-07-01", policy)
    assert decision["is_market_session_date_eligible"] is False
    assert decision["market_session_date_state"] == STATE_UNVERIFIED
    assert decision["calendar_coverage_state"] == "outside_supported_calendar_coverage"


def test_explicit_closed_date_is_ineligible():
    policy = build_declared_market_session_policy(
        eligible_dates=["2026-06-01"],
        closed_dates=["2026-06-02"],
        coverage_start="2026-06-01",
        coverage_end="2026-06-05",
    )
    decision = evaluate_market_session_date("2026-06-02", policy)
    assert decision["market_session_date_state"] == STATE_INELIGIBLE
    assert "closed" in decision["decision_reason"]


def test_market_session_policy_text_validator():
    assert "未来会涨" in validate_market_session_policy_text("未来会涨")
    assert validate_market_session_policy_text("日期策略只描述离线采集日期边界。") == []
