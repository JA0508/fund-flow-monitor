from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.collection_policy import (
    decide_collection_eligibility,
    find_active_session,
    get_default_collection_policy,
    parse_policy_time,
    validate_collection_policy_text,
)
from src.market_session_policy import build_declared_market_session_policy


def _dt(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=ZoneInfo("Asia/Shanghai"))


def test_default_policy_has_bounded_sessions():
    policy = get_default_collection_policy()
    assert policy["enabled"] is True
    assert policy["min_interval_seconds"] > 0
    assert policy["max_attempts_per_session"] > 0
    assert len(policy["sessions"]) == 2


def test_parse_policy_time_accepts_hour_minute():
    assert parse_policy_time("09:30").hour == 9
    assert parse_policy_time("09:30").minute == 30


def test_find_active_session_morning():
    policy = get_default_collection_policy()
    active = find_active_session(policy, _dt("2026-06-01T10:00:00"))
    assert active is not None
    assert active["name"] == "morning_session"


def _eligible_policy():
    policy = get_default_collection_policy()
    policy["market_session_policy"] = build_declared_market_session_policy(
        eligible_dates=["2026-06-01"],
        coverage_start="2026-06-01",
        coverage_end="2026-06-02",
    )
    return policy


def test_decision_outside_session():
    decision = decide_collection_eligibility(_eligible_policy(), now=_dt("2026-06-01T08:00:00"))
    assert decision["eligible"] is False
    assert decision["policy_status"] == "outside_session"
    assert decision["seconds_until_next_eligible"] is None
    assert decision["seconds_until_next_clock_session"] is not None


def test_clock_window_is_insufficient_without_market_session_date():
    decision = decide_collection_eligibility(now=_dt("2026-06-01T10:00:00"))
    assert decision["eligible"] is False
    assert decision["policy_status"] == "market_calendar_unverified"


def test_market_session_ineligible_date_blocks_before_clock_session():
    policy = _eligible_policy()
    decision = decide_collection_eligibility(policy, now=_dt("2026-06-02T10:00:00"))
    assert decision["eligible"] is False
    assert decision["policy_status"] == "market_session_date_ineligible"
    assert decision["active_session_name"] is None


def test_decision_disabled():
    policy = get_default_collection_policy()
    policy["enabled"] = False
    decision = decide_collection_eligibility(policy, now=_dt("2026-06-01T10:00:00"))
    assert decision["eligible"] is False
    assert decision["policy_status"] == "disabled"


def test_decision_too_soon_since_success():
    decision = decide_collection_eligibility(
        _eligible_policy(),
        now=_dt("2026-06-01T10:02:00"),
        latest_success_at=_dt("2026-06-01T10:00:00"),
    )
    assert decision["eligible"] is False
    assert decision["policy_status"] == "too_soon_since_success"
    assert decision["seconds_until_next_eligible"] == 180


def test_decision_max_attempts_reached():
    policy = _eligible_policy()
    decision = decide_collection_eligibility(
        policy,
        now=_dt("2026-06-01T10:00:00"),
        attempts_in_active_session=policy["max_attempts_per_session"],
    )
    assert decision["eligible"] is False
    assert decision["policy_status"] == "max_attempts_reached"


def test_decision_eligible():
    decision = decide_collection_eligibility(_eligible_policy(), now=_dt("2026-06-01T10:00:00"))
    assert decision["eligible"] is True
    assert decision["policy_status"] == "eligible"


def test_policy_text_validator():
    assert validate_collection_policy_text("未来会涨") == ["未来会涨"]
    assert validate_collection_policy_text("采集策略只描述历史快照写入窗口。") == []
