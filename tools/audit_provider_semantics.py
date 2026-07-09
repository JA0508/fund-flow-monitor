from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.provider_comparability import evaluate_provider_continuity_eligibility, validate_provider_comparability_text  # noqa: E402
from src.provider_contracts import render_provider_contract_human, validate_provider_contract_text  # noqa: E402
from src.provider_network_diagnostics import build_provider_network_diagnosis  # noqa: E402
from src.provider_registry import (  # noqa: E402
    build_provider_registry_summary,
    compare_registered_provider_contracts,
    get_primary_provider_contract,
    get_provider_contract,
    list_provider_contracts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit provider semantic contracts and continuity eligibility.")
    parser.add_argument("--registry", action="store_true", help="Show provider registry summary.")
    parser.add_argument("--primary", action="store_true", help="Show primary provider contract.")
    parser.add_argument("--candidate", help="Show one candidate provider contract by provider_id.")
    parser.add_argument("--compare", help="Compare PRIMARY_ID::CANDIDATE_ID.")
    parser.add_argument("--eligibility", action="store_true", help="Show continuity eligibility for all candidates.")
    parser.add_argument("--runtime-policy", default="primary_only", choices=["primary_only", "explicit_fallback"])
    parser.add_argument("--fallback-requested", action="store_true", help="Evaluate explicit fallback request semantics.")
    parser.add_argument("--diagnose-network", action="store_true", help="Run optional sanitized network diagnosis.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser


def _contract_or_error(provider_id: str) -> tuple[dict | None, list[str]]:
    contract = get_provider_contract(provider_id)
    if contract is None:
        return None, [f"Unknown provider_id: {provider_id}"]
    return contract.to_dict(), []


def build_audit_result(args: argparse.Namespace) -> dict:
    primary = get_primary_provider_contract()
    result: dict = {
        "network_used": bool(args.diagnose_network),
        "primary_provider_id": primary.provider_id,
        "primary_contract_id": primary.to_dict().get("semantic_contract_short_id"),
        "runtime_policy": args.runtime_policy,
        "fallback_requested": bool(args.fallback_requested),
        "registry_summary": None,
        "primary_contract": None,
        "candidate_contract": None,
        "comparability": None,
        "eligibility": None,
        "network_diagnosis": None,
        "errors": [],
        "warnings": [],
    }
    if args.registry:
        result["registry_summary"] = build_provider_registry_summary(runtime_policy=args.runtime_policy)
    if args.primary:
        result["primary_contract"] = primary.to_dict()
    if args.candidate:
        contract, errors = _contract_or_error(args.candidate)
        result["candidate_contract"] = contract
        result["errors"].extend(errors)
    if args.compare:
        if "::" not in args.compare:
            result["errors"].append("--compare must use PRIMARY_ID::CANDIDATE_ID")
        else:
            primary_id, candidate_id = args.compare.split("::", 1)
            result["comparability"] = compare_registered_provider_contracts(primary_id, candidate_id)
    if args.eligibility:
        rows = []
        for item in list_provider_contracts(include_primary=True):
            contract = get_provider_contract(item["provider_id"])
            rows.append(
                evaluate_provider_continuity_eligibility(
                    primary,
                    contract,
                    runtime_policy=args.runtime_policy,
                    fallback_requested=args.fallback_requested,
                )
            )
        result["eligibility"] = rows
    if args.diagnose_network:
        result["network_diagnosis"] = build_provider_network_diagnosis()
    text = json.dumps(result, ensure_ascii=False)
    result["forbidden_hits"] = sorted(set(validate_provider_contract_text(text) + validate_provider_comparability_text(text)))
    return result


def _print_text(result: dict) -> None:
    print("Provider semantic audit")
    print(f"  network_used: {result.get('network_used')}")
    print(f"  primary_provider_id: {result.get('primary_provider_id')}")
    print(f"  primary_contract_id: {result.get('primary_contract_id')}")
    if result.get("primary_contract"):
        print(f"  primary: {render_provider_contract_human(result['primary_contract'])}")
    if result.get("candidate_contract"):
        print(f"  candidate: {render_provider_contract_human(result['candidate_contract'])}")
    if result.get("registry_summary"):
        summary = result["registry_summary"]
        print(f"  candidates reviewed: {summary.get('candidate_count')}")
        print(f"  comparability counts: {summary.get('comparability_counts')}")
        print(f"  fallback eligible: {summary.get('fallback_eligible_provider_ids')}")
        print(f"  shadow only: {summary.get('shadow_only_provider_ids')}")
        print(f"  rejected: {summary.get('rejected_provider_ids')}")
    if result.get("comparability"):
        comparison = result["comparability"]
        print(f"  comparability: {comparison.get('comparability_state')}")
        print(f"  blocking differences: {comparison.get('blocking_differences')}")
        print(f"  unknown dimensions: {comparison.get('unknown_dimensions')}")
    if result.get("eligibility"):
        print("  eligibility:")
        for row in result["eligibility"]:
            comp = row.get("comparability", {})
            print(
                f"    {comp.get('candidate_provider_id')}: {row.get('semantic_eligibility')} "
                f"| runtime={row.get('runtime_policy')} | fallback_enabled={row.get('fallback_enabled')}"
            )
    if result.get("network_diagnosis"):
        diagnosis = result["network_diagnosis"]
        print(f"  network final classification: {diagnosis.get('final_classification')}")
    for warning in result.get("warnings", []):
        print(f"  warning: {warning}")
    for error in result.get("errors", []):
        print(f"  error: {error}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not any([args.registry, args.primary, args.candidate, args.compare, args.eligibility, args.diagnose_network]):
        args.registry = True
    result = build_audit_result(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_text(result)
    if result.get("forbidden_hits"):
        print(f"forbidden_hits: {result.get('forbidden_hits')}")
        return 3
    if result.get("errors"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
