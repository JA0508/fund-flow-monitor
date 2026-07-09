from __future__ import annotations

from typing import Any

from src.provider_contracts import ProviderSemanticContract, UNKNOWN, validate_provider_contract_text


COMPARABILITY_STATES = ("equivalent", "conditionally_comparable", "non_equivalent", "unknown")
CONTINUITY_STATES = ("primary", "fallback_eligible", "shadow_only", "rejected_non_equivalent", "rejected_unknown", "disabled")
RUNTIME_POLICIES = ("primary_only", "explicit_fallback")

COMPARISON_DIMENSIONS = (
    "metric_family",
    "metric_semantics",
    "time_semantics",
    "capture_semantics",
    "row_grain",
    "universe_semantics",
    "value_semantics",
    "unit",
    "sign_semantics",
)

BLOCKING_DIMENSIONS = ("metric_family", "metric_semantics", "row_grain", "value_semantics", "unit", "sign_semantics")
CONDITIONAL_DIMENSIONS = ("time_semantics", "capture_semantics", "universe_semantics")


def _as_dict(contract: ProviderSemanticContract | dict[str, Any]) -> dict[str, Any]:
    return contract.to_dict() if isinstance(contract, ProviderSemanticContract) else dict(contract)


def _norm(value: Any) -> str:
    if value is None:
        return UNKNOWN
    return " ".join(str(value).strip().lower().split()) or UNKNOWN


def compare_provider_contracts(
    primary: ProviderSemanticContract | dict[str, Any],
    candidate: ProviderSemanticContract | dict[str, Any],
) -> dict:
    left = _as_dict(primary)
    right = _as_dict(candidate)
    matching: list[str] = []
    differing: list[str] = []
    unknown: list[str] = []
    blocking: list[str] = []
    notes: list[str] = []
    for dimension in COMPARISON_DIMENSIONS:
        a = _norm(left.get(dimension))
        b = _norm(right.get(dimension))
        if a == UNKNOWN or b == UNKNOWN:
            unknown.append(dimension)
        elif a == b:
            matching.append(dimension)
        else:
            differing.append(dimension)
            if dimension in BLOCKING_DIMENSIONS:
                blocking.append(dimension)
    if blocking:
        classification = "non_equivalent"
        reason = "One or more blocking semantic dimensions differ."
    elif unknown:
        classification = "unknown"
        reason = "Insufficient factual evidence to classify all required semantic dimensions."
    elif differing:
        conditional = [item for item in differing if item in CONDITIONAL_DIMENSIONS]
        if conditional and len(conditional) == len(differing):
            classification = "conditionally_comparable"
            reason = "Related source with known non-blocking semantic differences; do not silently substitute."
        else:
            classification = "non_equivalent"
            reason = "Semantic differences are too material for continuity."
    else:
        classification = "equivalent"
        reason = "Required semantic dimensions match the primary contract."
    if _norm(left.get("api_name")) == _norm(right.get("api_name")) and classification != "equivalent":
        notes.append("Same or similar API name was not treated as equivalence.")
    if _norm(left.get("provider_id")) == _norm(right.get("provider_id")):
        notes.append("Candidate is the primary contract itself.")
    return {
        "primary_provider_id": left.get("provider_id"),
        "candidate_provider_id": right.get("provider_id"),
        "comparability_state": classification,
        "classification_reason": reason,
        "matching_dimensions": matching,
        "differing_dimensions": differing,
        "unknown_dimensions": unknown,
        "blocking_differences": blocking,
        "notes": notes,
        "numeric_score": None,
    }


def evaluate_provider_continuity_eligibility(
    primary: ProviderSemanticContract | dict[str, Any],
    candidate: ProviderSemanticContract | dict[str, Any],
    runtime_policy: str = "primary_only",
    fallback_requested: bool = False,
    enabled: bool = True,
) -> dict:
    runtime_policy = runtime_policy if runtime_policy in RUNTIME_POLICIES else "primary_only"
    if not enabled:
        return {
            "continuity_state": "disabled",
            "semantic_eligibility": "disabled",
            "runtime_policy": runtime_policy,
            "fallback_enabled": False,
            "fallback_requested": bool(fallback_requested),
            "reason": "Provider is disabled by configuration.",
        }
    comparison = compare_provider_contracts(primary, candidate)
    candidate_id = comparison.get("candidate_provider_id")
    primary_id = comparison.get("primary_provider_id")
    state = comparison.get("comparability_state")
    if candidate_id == primary_id:
        continuity_state = "primary"
        semantic_eligibility = "primary"
        reason = "This is the explicitly configured primary provider."
    elif state == "equivalent":
        semantic_eligibility = "fallback_eligible"
        fallback_allowed = bool(fallback_requested and runtime_policy == "explicit_fallback")
        continuity_state = "fallback_eligible"
        reason = "Semantically equivalent candidate; fallback still requires explicit runtime policy."
    elif state == "conditionally_comparable":
        semantic_eligibility = "shadow_only"
        fallback_allowed = False
        continuity_state = "shadow_only"
        reason = "Candidate is related but has known semantic differences; use shadow-only comparison."
    elif state == "non_equivalent":
        semantic_eligibility = "rejected_non_equivalent"
        fallback_allowed = False
        continuity_state = "rejected_non_equivalent"
        reason = "Candidate has blocking semantic differences."
    else:
        semantic_eligibility = "rejected_unknown"
        fallback_allowed = False
        continuity_state = "rejected_unknown"
        reason = "Candidate semantics are unknown or incomplete."
    if candidate_id == primary_id:
        fallback_allowed = False
    elif state == "equivalent":
        fallback_allowed = bool(fallback_requested and runtime_policy == "explicit_fallback")
    return {
        "continuity_state": continuity_state,
        "semantic_eligibility": semantic_eligibility,
        "runtime_policy": runtime_policy,
        "fallback_enabled": bool(fallback_allowed),
        "fallback_requested": bool(fallback_requested),
        "reason": reason,
        "comparability": comparison,
    }


def validate_provider_comparability_text(text: str) -> list[str]:
    return validate_provider_contract_text(text)
