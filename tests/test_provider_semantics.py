from __future__ import annotations

from dataclasses import replace

from src.provider_comparability import compare_provider_contracts, evaluate_provider_continuity_eligibility
from src.provider_contracts import build_provider_contract_fingerprint, build_primary_provider_contract, render_provider_contract_human
from src.provider_registry import build_provider_registry_summary, get_primary_provider_contract, get_provider_contract, list_provider_contracts


def test_provider_contract_fingerprint_deterministic_and_formatting_insensitive():
    contract = build_primary_provider_contract()
    same = replace(contract, metric_semantics=f"  {contract.metric_semantics}   ")
    assert build_provider_contract_fingerprint(contract) == build_provider_contract_fingerprint(same)


def test_provider_contract_semantic_change_changes_fingerprint():
    contract = build_primary_provider_contract()
    changed = replace(contract, metric_semantics="different semantic fact")
    assert build_provider_contract_fingerprint(contract) != build_provider_contract_fingerprint(changed)


def test_primary_contract_exists_and_human_readable():
    contract = get_primary_provider_contract()
    assert contract.provider_id
    assert contract.to_dict()["semantic_contract_short_id"]
    assert "stock_sector_fund_flow_rank" in render_provider_contract_human(contract)


def test_registry_lists_candidates_offline():
    contracts = list_provider_contracts()
    assert any(item["provider_id"] == get_primary_provider_contract().provider_id for item in contracts)
    assert len(contracts) >= 2


def test_equivalent_contract_classification():
    primary = build_primary_provider_contract()
    result = compare_provider_contracts(primary, primary)
    assert result["comparability_state"] == "equivalent"


def test_conditionally_comparable_concept_candidate():
    primary = get_primary_provider_contract()
    candidate = get_provider_contract("akshare_eastmoney_sector_fund_flow_rank_today_concept")
    result = compare_provider_contracts(primary, candidate)
    assert result["comparability_state"] == "conditionally_comparable"
    assert "universe_semantics" in result["differing_dimensions"]
    eligibility = evaluate_provider_continuity_eligibility(primary, candidate, runtime_policy="explicit_fallback", fallback_requested=True)
    assert eligibility["semantic_eligibility"] == "shadow_only"
    assert eligibility["fallback_enabled"] is False


def test_non_equivalent_stock_candidate():
    primary = get_primary_provider_contract()
    candidate = get_provider_contract("akshare_eastmoney_main_fund_flow_stock_universe")
    result = compare_provider_contracts(primary, candidate)
    assert result["comparability_state"] == "non_equivalent"
    assert result["blocking_differences"]


def test_unknown_candidate_semantics():
    primary = get_primary_provider_contract()
    candidate = replace(primary, provider_id="unknown_candidate", metric_semantics="unknown")
    result = compare_provider_contracts(primary, candidate)
    assert result["comparability_state"] == "unknown"
    assert "metric_semantics" in result["unknown_dimensions"]


def test_continuity_primary_and_default_policy():
    primary = get_primary_provider_contract()
    result = evaluate_provider_continuity_eligibility(primary, primary)
    assert result["continuity_state"] == "primary"
    assert result["runtime_policy"] == "primary_only"
    assert result["fallback_enabled"] is False


def test_continuity_equivalent_requires_explicit_fallback_policy():
    primary = get_primary_provider_contract()
    clone = replace(primary, provider_id="equivalent_clone")
    default_result = evaluate_provider_continuity_eligibility(primary, clone)
    explicit_result = evaluate_provider_continuity_eligibility(primary, clone, runtime_policy="explicit_fallback", fallback_requested=True)
    assert default_result["semantic_eligibility"] == "fallback_eligible"
    assert default_result["fallback_enabled"] is False
    assert explicit_result["fallback_enabled"] is True


def test_continuity_rejects_non_equivalent():
    primary = get_primary_provider_contract()
    candidate = get_provider_contract("akshare_eastmoney_market_fund_flow")
    result = evaluate_provider_continuity_eligibility(primary, candidate, runtime_policy="explicit_fallback", fallback_requested=True)
    assert result["continuity_state"] == "rejected_non_equivalent"
    assert result["fallback_enabled"] is False


def test_registry_summary_no_silent_fallback():
    summary = build_provider_registry_summary()
    assert summary["runtime_policy"] == "primary_only"
    assert summary["fallback_enabled"] is False
    assert summary["candidate_count"] >= 1
