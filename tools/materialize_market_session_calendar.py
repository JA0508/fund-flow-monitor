from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import TIMEZONE
from src.market_session_policy import (
    ALIGNMENT_PROVIDER_UNIFIED,
    DEFAULT_MARKET_SESSION_CALENDAR_PATH,
    SOURCE_CLASSIFICATION_PROVIDER_DERIVED,
    build_policy_from_market_session_reference,
    load_market_session_reference,
    validate_market_session_reference,
)


AKSHARE_FUNCTION = "tool_trade_date_hist_sina"
SINA_SOURCE_URL = "https://finance.sina.com.cn/realstock/company/klc_td_sh.txt"


def _date_text(value: object) -> str:
    return str(value)[:10]


def _safe_output_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except Exception:
        return str(path)


def _load_akshare_sina_dates() -> list[str]:
    import akshare as ak

    df = ak.tool_trade_date_hist_sina()
    if df is None or df.empty or "trade_date" not in df.columns:
        raise RuntimeError("AKShare tool_trade_date_hist_sina returned no trade_date column.")
    return sorted({_date_text(value) for value in df["trade_date"].dropna().tolist()})


def build_provider_derived_reference(eligible_dates: list[str]) -> dict:
    if not eligible_dates:
        raise ValueError("eligible_dates cannot be empty.")
    source_identity = "akshare_tool_trade_date_hist_sina__sina_klc_td_sh"
    return {
        "schema_version": "market_session_calendar_v1",
        "calendar_name": "provider_derived_mainland_a_share_trading_dates",
        "calendar_source": "akshare_sina_trade_date_hist",
        "calendar_source_identity": source_identity,
        "source_reference_identity": source_identity,
        "source_strategy": "provider_derived_materialization_with_explicit_non_authoritative_provenance",
        "source_classification": SOURCE_CLASSIFICATION_PROVIDER_DERIVED,
        "market_scope": "provider_derived_mainland_a_share_observation_session_domain",
        "timezone": TIMEZONE,
        "calendar_semantics": (
            "Provider-derived trading-date list used as an offline date gate for the project's "
            "A-share industry fund-flow observation-session domain. It is not exchange-authoritative."
        ),
        "coverage_start": eligible_dates[0],
        "coverage_end": eligible_dates[-1],
        "coverage_semantics": "Within coverage, only eligible_session_dates are market-session eligible.",
        "closure_semantics": "Dates absent from eligible_session_dates inside coverage are not eligible.",
        "materialization_method": "manual_bounded_akshare_sina_fetch_then_repository_review",
        "materialized_at": datetime.now().replace(microsecond=0).isoformat(),
        "eligible_session_dates": eligible_dates,
        "explicit_closed_dates": [],
        "source_references": [
            {
                "source_classification": SOURCE_CLASSIFICATION_PROVIDER_DERIVED,
                "source_name": "AKShare tool_trade_date_hist_sina",
                "source_identity": AKSHARE_FUNCTION,
                "source_locator": SINA_SOURCE_URL,
                "identity_defining": True,
                "notes": "Underlying source is Sina Finance; this reference is provider-derived, not exchange-authoritative.",
            },
            {
                "source_classification": "exchange_published_cross_check",
                "source_name": "Shanghai Stock Exchange 2026 Dragon Boat Festival closure announcement",
                "source_identity": "sse_2026_duanwu_closure_notice_c_20260611_10821419",
                "source_locator": "https://www.sse.com.cn/disclosure/announcement/general/c/c_20260611_10821419.shtml",
                "identity_defining": False,
                "notes": "Reviewed prose source for one 2026 holiday closure / reopen fact.",
            },
            {
                "source_classification": "exchange_published_cross_check",
                "source_name": "Shenzhen Stock Exchange 2026 Dragon Boat Festival closure notice",
                "source_identity": "szse_2026_duanwu_closure_notice_t20260611_620979",
                "source_locator": "https://www.szse.cn/disclosure/notice/general/t20260611_620979.html",
                "identity_defining": False,
                "notes": "Reviewed prose source for one 2026 holiday closure / reopen fact.",
            },
        ],
        "exchange_reconciliation": {
            "required_project_scope": "A-share industry fund-flow observation-session domain spanning the broader mainland stock market.",
            "cross_exchange_alignment_state": ALIGNMENT_PROVIDER_UNIFIED,
            "sse_eligible_date_count": None,
            "szse_eligible_date_count": None,
            "common_eligible_date_count": None,
            "sse_only_date_count": None,
            "szse_only_date_count": None,
            "sse_only_dates": [],
            "szse_only_dates": [],
            "notes": (
                "The production reference is a provider-derived unified trading-date list. "
                "It does not separately enumerate SSE and SZSE eligible domains, so it must not be described as exchange-authoritative."
            ),
        },
        "display_name": "Provider-derived A-share trading-date calendar",
        "notes": [
            "Runtime policy evaluation reads this JSON offline.",
            "Normal collection, Streamlit rendering, CI and evidence audits must not refresh this source.",
        ],
    }


def summarize_reference(reference: dict, previous_reference: dict | None = None) -> dict:
    policy = build_policy_from_market_session_reference(reference)
    previous_policy = build_policy_from_market_session_reference(previous_reference) if previous_reference else None
    validation = validate_market_session_reference(reference)
    eligible = set(reference.get("eligible_session_dates") or [])
    previous_eligible = set(previous_reference.get("eligible_session_dates") or []) if previous_reference else set()
    closed = set(reference.get("explicit_closed_dates") or [])
    previous_closed = set(previous_reference.get("explicit_closed_dates") or []) if previous_reference else set()
    reconciliation = reference.get("exchange_reconciliation") or {}
    eligible_added = sorted(eligible - previous_eligible)
    eligible_removed = sorted(previous_eligible - eligible)
    closed_added = sorted(closed - previous_closed)
    closed_removed = sorted(previous_closed - closed)
    return {
        "source_strategy": reference.get("source_strategy"),
        "source_classification": reference.get("source_classification"),
        "market_scope": reference.get("market_scope"),
        "coverage_start": reference.get("coverage_start"),
        "coverage_end": reference.get("coverage_end"),
        "eligible_date_count": len(eligible),
        "closed_date_count": len(closed),
        "calendar_policy_identity": policy.get("calendar_policy_identity"),
        "previous_calendar_policy_identity": previous_policy.get("calendar_policy_identity") if previous_policy else None,
        "eligible_dates_added_count": len(eligible_added),
        "eligible_dates_removed_count": len(eligible_removed),
        "closed_dates_added_count": len(closed_added),
        "closed_dates_removed_count": len(closed_removed),
        "eligible_dates_added_preview": eligible_added[:20],
        "eligible_dates_removed_preview": eligible_removed[:20],
        "closed_dates_added_preview": closed_added[:20],
        "closed_dates_removed_preview": closed_removed[:20],
        "cross_exchange_alignment_state": reconciliation.get("cross_exchange_alignment_state"),
        "validation": {
            "valid": validation.get("valid"),
            "error_count": validation.get("error_count"),
            "warning_count": validation.get("warning_count"),
            "errors": validation.get("errors", []),
            "warnings": validation.get("warnings", []),
            "eligible_date_count": len(validation.get("eligible_dates", [])),
            "closed_date_count": len(validation.get("closed_dates", [])),
            "coverage_start": validation.get("coverage_start"),
            "coverage_end": validation.get("coverage_end"),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize or validate the local market-session calendar reference.")
    parser.add_argument("--source", default="akshare-sina", choices=["akshare-sina"])
    parser.add_argument("--output", default=DEFAULT_MARKET_SESSION_CALENDAR_PATH)
    parser.add_argument("--write", action="store_true", help="Write the validated reference to --output.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch/build and report without writing.")
    parser.add_argument("--validate-only", action="store_true", help="Validate the existing --output reference without fetching.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_path = PROJECT_ROOT / args.output
    previous = load_market_session_reference(out_path) if out_path.exists() else None

    try:
        if args.validate_only:
            if previous is None:
                raise FileNotFoundError(str(out_path))
            reference = previous
        else:
            dates = _load_akshare_sina_dates()
            reference = build_provider_derived_reference(dates)
        summary = summarize_reference(reference, previous_reference=previous)
        validation = summary.get("validation") or {}
        if not validation.get("valid"):
            raise ValueError("; ".join(validation.get("errors", [])))
        wrote = False
        if args.write and not args.dry_run and not args.validate_only:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(reference, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            wrote = True
        result = {
            "ok": True,
            "output": _safe_output_label(out_path),
            "wrote": wrote,
            **summary,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "output": _safe_output_label(out_path),
            "wrote": False,
            "error": str(exc),
        }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"market_session_calendar_ok: {result.get('ok')}")
        print(f"output: {result.get('output')}")
        print(f"wrote: {result.get('wrote')}")
        print(f"source_classification: {result.get('source_classification')}")
        print(f"market_scope: {result.get('market_scope')}")
        print(f"coverage: {result.get('coverage_start')} -> {result.get('coverage_end')}")
        print(f"eligible_date_count: {result.get('eligible_date_count')}")
        print(f"calendar_policy_identity: {result.get('calendar_policy_identity')}")
        print(f"cross_exchange_alignment_state: {result.get('cross_exchange_alignment_state')}")
        if not result.get("ok"):
            print(f"error: {result.get('error')}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
