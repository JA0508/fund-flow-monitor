from __future__ import annotations

from src.provider_comparability import compare_provider_contracts, evaluate_provider_continuity_eligibility
from src.provider_contracts import (
    PRIMARY_PROVIDER_ID,
    ProviderSemanticContract,
    build_primary_provider_contract,
    build_provider_contract_short_id,
)


def _candidate_contracts() -> tuple[ProviderSemanticContract, ...]:
    primary = build_primary_provider_contract()
    return (
        primary,
        ProviderSemanticContract(
            provider_id="akshare_eastmoney_sector_fund_flow_rank_today_concept",
            provider_name="AKShare / Eastmoney",
            upstream_origin="Eastmoney push2.eastmoney.com / data.eastmoney.com 板块资金流",
            api_name="ak.stock_sector_fund_flow_rank",
            api_arguments={"indicator": "今日", "sector_type": "概念资金流"},
            metric_family=primary.metric_family,
            metric_semantics=primary.metric_semantics,
            time_semantics=primary.time_semantics,
            capture_semantics=primary.capture_semantics,
            row_grain=primary.row_grain,
            universe_semantics="Eastmoney 概念资金流 concept universe exposed through AKShare sector_type=概念资金流.",
            value_semantics=primary.value_semantics,
            unit=primary.unit,
            sign_semantics=primary.sign_semantics,
            timezone=primary.timezone,
            required_source_fields=primary.required_source_fields,
            internal_contract_name="normalized_concept_flow_snapshot_v1",
            normalization_path=primary.normalization_path,
            contract_version="v1",
            source_notes=("Related Eastmoney board-flow source, but concept universe is not the same analytical fact as industry sector universe.",),
        ),
        ProviderSemanticContract(
            provider_id="akshare_eastmoney_sector_fund_flow_rank_5d_industry",
            provider_name="AKShare / Eastmoney",
            upstream_origin=primary.upstream_origin,
            api_name="ak.stock_sector_fund_flow_rank",
            api_arguments={"indicator": "5日", "sector_type": "行业资金流"},
            metric_family=primary.metric_family,
            metric_semantics="Eastmoney industry-sector fund-flow ranking for provider 5日 indicator.",
            time_semantics="provider multi-day 5日 indicator; not the same as 今日 as-of-capture snapshot.",
            capture_semantics=primary.capture_semantics,
            row_grain=primary.row_grain,
            universe_semantics=primary.universe_semantics,
            value_semantics="5日主力净流入-净额; related but not same analytical fact as 今日主力净流入-净额.",
            unit=primary.unit,
            sign_semantics=primary.sign_semantics,
            timezone=primary.timezone,
            required_source_fields=("名称", "5日主力净流入-净额"),
            internal_contract_name="normalized_sector_flow_5d_snapshot_v1",
            normalization_path="not currently normalized by project primary path",
            contract_version="v1",
            source_notes=("Same AKShare function with a different indicator window; not silent fallback eligible for 今日 continuity.",),
        ),
        ProviderSemanticContract(
            provider_id="akshare_eastmoney_sector_fund_flow_summary_industry",
            provider_name="AKShare / Eastmoney",
            upstream_origin="Eastmoney sector fund-flow summary pages",
            api_name="ak.stock_sector_fund_flow_summary",
            api_arguments={"symbol": "行业名称"},
            metric_family="sector_fund_flow",
            metric_semantics="symbol-specific sector fund-flow summary; exact continuity semantics versus ranking endpoint not proven.",
            time_semantics="unknown",
            capture_semantics="unknown",
            row_grain="rows for stocks or members within one selected sector/symbol, not one row per industry sector universe",
            universe_semantics="single selected sector/symbol detail universe",
            value_semantics="unknown",
            unit="unknown",
            sign_semantics="unknown",
            timezone="Asia/Shanghai capture timestamp if normalized by project",
            required_source_fields=(),
            internal_contract_name="candidate_only_not_normalized",
            normalization_path="not implemented",
            contract_version="v1",
            source_notes=("Candidate discovered from installed AKShare source; insufficient evidence for continuity.",),
        ),
        ProviderSemanticContract(
            provider_id="akshare_eastmoney_sector_fund_flow_hist_industry_symbol",
            provider_name="AKShare / Eastmoney",
            upstream_origin="Eastmoney sector fund-flow history pages",
            api_name="ak.stock_sector_fund_flow_hist",
            api_arguments={"symbol": "行业名称"},
            metric_family="sector_fund_flow_history",
            metric_semantics="historical series for one selected sector symbol, not cross-sector ranking snapshot.",
            time_semantics="historical daily rows by selected symbol",
            capture_semantics="provider historical retrieval rather than project manual capture snapshot",
            row_grain="one row per historical date for one sector symbol",
            universe_semantics="single sector symbol history",
            value_semantics="historical fund-flow fields for selected symbol",
            unit="unknown",
            sign_semantics="unknown",
            timezone="unknown",
            required_source_fields=(),
            internal_contract_name="candidate_only_not_normalized",
            normalization_path="not implemented",
            contract_version="v1",
            source_notes=("Useful for separate research, not the same continuity path as cross-sector captured ranking.",),
        ),
        ProviderSemanticContract(
            provider_id="akshare_eastmoney_concept_fund_flow_hist_symbol",
            provider_name="AKShare / Eastmoney",
            upstream_origin="Eastmoney concept fund-flow history pages",
            api_name="ak.stock_concept_fund_flow_hist",
            api_arguments={"symbol": "概念名称"},
            metric_family="concept_fund_flow_history",
            metric_semantics="historical series for one selected concept symbol.",
            time_semantics="historical daily rows by selected concept symbol",
            capture_semantics="provider historical retrieval rather than project manual capture snapshot",
            row_grain="one row per historical date for one concept symbol",
            universe_semantics="single concept symbol history",
            value_semantics="historical concept fund-flow fields for selected symbol",
            unit="unknown",
            sign_semantics="unknown",
            timezone="unknown",
            required_source_fields=(),
            internal_contract_name="candidate_only_not_normalized",
            normalization_path="not implemented",
            contract_version="v1",
            source_notes=("Concept history is not equivalent to industry-sector 今日 ranking snapshot.",),
        ),
        ProviderSemanticContract(
            provider_id="akshare_eastmoney_market_fund_flow",
            provider_name="AKShare / Eastmoney",
            upstream_origin="Eastmoney market-wide fund-flow pages",
            api_name="ak.stock_market_fund_flow",
            api_arguments={},
            metric_family="market_fund_flow",
            metric_semantics="market-wide fund flow, not sector/theme board flow.",
            time_semantics="unknown",
            capture_semantics="provider retrieval",
            row_grain="market-level or market-series rows",
            universe_semantics="whole-market aggregate rather than sector universe",
            value_semantics="market-level fund-flow fields",
            unit="unknown",
            sign_semantics="unknown",
            timezone="unknown",
            required_source_fields=(),
            internal_contract_name="candidate_only_not_normalized",
            normalization_path="not implemented",
            contract_version="v1",
            source_notes=("Materially different fact from sector-level fund-flow ranking.",),
        ),
        ProviderSemanticContract(
            provider_id="akshare_eastmoney_main_fund_flow_stock_universe",
            provider_name="AKShare / Eastmoney",
            upstream_origin="Eastmoney stock fund-flow pages",
            api_name="ak.stock_main_fund_flow",
            api_arguments={"symbol": "全部股票"},
            metric_family="stock_fund_flow",
            metric_semantics="individual-stock main fund-flow ranking.",
            time_semantics="unknown",
            capture_semantics="provider retrieval",
            row_grain="one row per stock",
            universe_semantics="stock universe, not sector board universe",
            value_semantics="stock-level fund-flow fields",
            unit="unknown",
            sign_semantics="unknown",
            timezone="unknown",
            required_source_fields=(),
            internal_contract_name="candidate_only_not_normalized",
            normalization_path="not implemented",
            contract_version="v1",
            source_notes=("Stock-level source is not a silent substitute for sector-level board flow.",),
        ),
    )


_REGISTRY = {contract.provider_id: contract for contract in _candidate_contracts()}


def get_primary_provider_contract() -> ProviderSemanticContract:
    return _REGISTRY[PRIMARY_PROVIDER_ID]


def list_provider_contracts(include_primary: bool = True) -> list[dict]:
    contracts = list(_REGISTRY.values())
    if not include_primary:
        contracts = [contract for contract in contracts if contract.provider_id != PRIMARY_PROVIDER_ID]
    return [contract.to_dict() for contract in sorted(contracts, key=lambda item: item.provider_id)]


def get_provider_contract(provider_id: str) -> ProviderSemanticContract | None:
    return _REGISTRY.get(str(provider_id or ""))


def compare_registered_provider_contracts(primary_id: str, candidate_id: str) -> dict:
    primary = get_provider_contract(primary_id)
    candidate = get_provider_contract(candidate_id)
    if primary is None or candidate is None:
        return {
            "comparability_state": "unknown",
            "primary_provider_id": primary_id,
            "candidate_provider_id": candidate_id,
            "matching_dimensions": [],
            "differing_dimensions": [],
            "unknown_dimensions": ["provider_id"],
            "blocking_differences": [],
            "notes": ["Unknown provider ID."],
        }
    return compare_provider_contracts(primary, candidate)


def build_provider_registry_summary(runtime_policy: str = "primary_only") -> dict:
    primary = get_primary_provider_contract()
    contracts = list_provider_contracts(include_primary=True)
    comparisons = []
    eligibility = []
    counts = {"equivalent": 0, "conditionally_comparable": 0, "non_equivalent": 0, "unknown": 0}
    for item in contracts:
        if item["provider_id"] == primary.provider_id:
            continue
        candidate = get_provider_contract(item["provider_id"])
        comparison = compare_provider_contracts(primary, candidate)
        counts[comparison["comparability_state"]] += 1
        comparisons.append(comparison)
        eligibility.append(evaluate_provider_continuity_eligibility(primary, candidate, runtime_policy=runtime_policy))
    return {
        "primary_provider_id": primary.provider_id,
        "primary_contract_id": build_provider_contract_short_id(primary),
        "runtime_policy": runtime_policy,
        "fallback_enabled": False,
        "candidate_count": len(contracts) - 1,
        "comparability_counts": counts,
        "fallback_eligible_provider_ids": [
            item["comparability"]["candidate_provider_id"]
            for item in eligibility
            if item.get("semantic_eligibility") == "fallback_eligible"
        ],
        "shadow_only_provider_ids": [
            item["comparability"]["candidate_provider_id"]
            for item in eligibility
            if item.get("semantic_eligibility") == "shadow_only"
        ],
        "rejected_provider_ids": [
            item["comparability"]["candidate_provider_id"]
            for item in eligibility
            if str(item.get("semantic_eligibility", "")).startswith("rejected")
        ],
        "comparisons": comparisons,
        "eligibility": eligibility,
    }


def infer_provider_contract_id(provider: object, api_name: object, sector_type: object | None = None, data_mode: object | None = None) -> str:
    provider_text = str(provider or "").strip()
    api_text = str(api_name or "").strip()
    sector_text = str(sector_type or "").strip()
    mode_text = str(data_mode or "").upper()
    if mode_text == "SAMPLE":
        return "sample_synthetic_demo_contract"
    if provider_text == "AKShare / Eastmoney" and api_text in {"stock_sector_fund_flow_rank", "ak.stock_sector_fund_flow_rank"}:
        if sector_text == "概念资金流":
            return "akshare_eastmoney_sector_fund_flow_rank_today_concept"
        return PRIMARY_PROVIDER_ID
    return "unknown_provider_contract"
