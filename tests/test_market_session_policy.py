from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from src.market_session_policy import (
    ALIGNMENT_ALIGNED,
    ALIGNMENT_DIVERGENT,
    ALIGNMENT_PROVIDER_UNIFIED,
    SOURCE_CLASSIFICATION_PROVIDER_DERIVED,
    STATE_ELIGIBLE,
    STATE_INELIGIBLE,
    STATE_UNVERIFIED,
    build_market_session_policy_identity,
    build_declared_market_session_policy,
    build_policy_from_market_session_reference,
    evaluate_market_session_date,
    get_conservative_market_session_policy,
    get_default_market_session_policy,
    load_market_session_policy_from_reference,
    reconcile_exchange_session_domains,
    validate_market_session_reference,
    validate_market_session_policy_text,
)


def _reference(**overrides):
    data = {
        "schema_version": "market_session_calendar_v1",
        "calendar_source": "unit_test_calendar",
        "calendar_source_identity": "unit_test_calendar_v1",
        "source_reference_identity": "unit_test_reference_v1",
        "source_strategy": "unit_test_materialization",
        "source_classification": SOURCE_CLASSIFICATION_PROVIDER_DERIVED,
        "market_scope": "unit_test_a_share_observation_domain",
        "timezone": "Asia/Shanghai",
        "calendar_semantics": "Unit-test offline reference.",
        "coverage_start": "2026-06-01",
        "coverage_end": "2026-06-12",
        "eligible_session_dates": ["2026-06-01", "2026-06-03", "2026-06-10"],
        "explicit_closed_dates": ["2026-06-02"],
        "exchange_reconciliation": {
            "cross_exchange_alignment_state": ALIGNMENT_PROVIDER_UNIFIED,
        },
    }
    data.update(overrides)
    return data


def test_conservative_policy_is_unverified_when_reference_absent():
    policy = get_conservative_market_session_policy()
    decision = evaluate_market_session_date("2026-06-01", policy)
    assert decision["is_market_session_date_eligible"] is False
    assert decision["market_session_date_state"] == STATE_UNVERIFIED
    assert decision["network_used"] is False


def test_default_policy_loads_materialized_reference_without_network():
    policy = get_default_market_session_policy()
    decision = evaluate_market_session_date("2026-07-13", policy)
    assert decision["is_market_session_date_eligible"] is True
    assert decision["market_session_date_state"] == STATE_ELIGIBLE
    assert decision["source_classification"] == SOURCE_CLASSIFICATION_PROVIDER_DERIVED
    assert decision["cross_exchange_alignment_state"] == ALIGNMENT_PROVIDER_UNIFIED
    assert decision["network_used"] is False


def test_default_policy_does_not_use_weekday_heuristic_for_weekend():
    policy = get_default_market_session_policy()
    decision = evaluate_market_session_date("2026-07-11", policy)
    assert decision["is_market_session_date_eligible"] is False
    assert decision["market_session_date_state"] == STATE_INELIGIBLE


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


def test_reference_policy_can_be_loaded_from_temp_json(tmp_path):
    path = tmp_path / "calendar.json"
    path.write_text(json.dumps(_reference(), ensure_ascii=False), encoding="utf-8")
    policy = load_market_session_policy_from_reference(path)
    decision = evaluate_market_session_date("2026-06-10", policy)
    assert decision["is_market_session_date_eligible"] is True
    assert decision["calendar_source"] == "unit_test_calendar"
    assert decision["network_used"] is False


def test_future_date_provisioning_changes_conservative_unverified_to_eligible(tmp_path):
    date = "2026-06-10"
    conservative = evaluate_market_session_date(date, get_conservative_market_session_policy())
    path = tmp_path / "calendar.json"
    path.write_text(json.dumps(_reference(eligible_session_dates=[date]), ensure_ascii=False), encoding="utf-8")
    provisioned = evaluate_market_session_date(date, load_market_session_policy_from_reference(path))
    assert conservative["market_session_date_state"] == STATE_UNVERIFIED
    assert provisioned["market_session_date_state"] == STATE_ELIGIBLE


def test_reference_rejects_eligible_closed_overlap():
    report = validate_market_session_reference(
        _reference(eligible_session_dates=["2026-06-01"], explicit_closed_dates=["2026-06-01"])
    )
    assert report["valid"] is False
    assert any("both eligible and closed" in item for item in report["errors"])


def test_reference_rejects_malformed_dates():
    report = validate_market_session_reference(_reference(eligible_session_dates=["not-a-date"]))
    assert report["valid"] is False
    assert any("Invalid date values" in item for item in report["errors"])


def test_policy_identity_changes_with_eligible_date_change():
    a = build_policy_from_market_session_reference(_reference(eligible_session_dates=["2026-06-01"]))
    b = build_policy_from_market_session_reference(_reference(eligible_session_dates=["2026-06-03"]))
    assert build_market_session_policy_identity(a) != build_market_session_policy_identity(b)


def test_policy_identity_changes_with_closed_date_change():
    a = build_policy_from_market_session_reference(_reference(explicit_closed_dates=["2026-06-02"]))
    b = build_policy_from_market_session_reference(_reference(explicit_closed_dates=["2026-06-04"]))
    assert build_market_session_policy_identity(a) != build_market_session_policy_identity(b)


def test_policy_identity_is_stable_for_date_ordering():
    a = build_policy_from_market_session_reference(_reference(eligible_session_dates=["2026-06-10", "2026-06-01"]))
    b = build_policy_from_market_session_reference(_reference(eligible_session_dates=["2026-06-01", "2026-06-10"]))
    assert build_market_session_policy_identity(a) == build_market_session_policy_identity(b)


def test_policy_identity_ignores_display_metadata_and_materialized_at():
    a = build_policy_from_market_session_reference(
        _reference(display_name="A", materialized_at="2026-01-01T00:00:00")
    )
    b = build_policy_from_market_session_reference(
        _reference(display_name="B", materialized_at="2026-01-02T00:00:00")
    )
    assert build_market_session_policy_identity(a) == build_market_session_policy_identity(b)


def test_policy_identity_changes_with_source_identity():
    a = build_policy_from_market_session_reference(_reference(source_reference_identity="reference_a"))
    b = build_policy_from_market_session_reference(_reference(source_reference_identity="reference_b"))
    assert build_market_session_policy_identity(a) != build_market_session_policy_identity(b)


def test_reconcile_exchange_domains_aligned():
    report = reconcile_exchange_session_domains(
        ["2026-06-01", "2026-06-02"],
        ["2026-06-01", "2026-06-02"],
    )
    assert report["cross_exchange_alignment_state"] == ALIGNMENT_ALIGNED
    assert report["sse_only_dates"] == []
    assert report["szse_only_dates"] == []


def test_reconcile_exchange_domains_divergent():
    report = reconcile_exchange_session_domains(
        ["2026-06-01", "2026-06-02"],
        ["2026-06-01", "2026-06-03"],
        coverage_start="2026-06-01",
        coverage_end="2026-06-03",
    )
    assert report["cross_exchange_alignment_state"] == ALIGNMENT_DIVERGENT
    assert report["sse_only_dates"] == ["2026-06-02"]
    assert report["szse_only_dates"] == ["2026-06-03"]


def test_reference_inside_coverage_absent_date_is_ineligible_not_weekday_inferred():
    policy = build_policy_from_market_session_reference(_reference(eligible_session_dates=["2026-06-01"]))
    decision = evaluate_market_session_date("2026-06-03", policy)
    assert decision["market_session_date_state"] == STATE_INELIGIBLE


def test_reference_outside_coverage_is_unverified():
    policy = build_policy_from_market_session_reference(_reference())
    decision = evaluate_market_session_date("2027-01-04", policy)
    assert decision["market_session_date_state"] == STATE_UNVERIFIED
    assert decision["calendar_coverage_state"] == "outside_supported_calendar_coverage"
