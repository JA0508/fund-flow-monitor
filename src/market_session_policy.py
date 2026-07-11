from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from src.config import TIMEZONE


STATE_ELIGIBLE = "eligible_market_session_date"
STATE_INELIGIBLE = "market_session_date_ineligible"
STATE_UNVERIFIED = "market_calendar_unverified"

COVERAGE_DECLARED = "declared_calendar_coverage"
COVERAGE_OUTSIDE = "outside_supported_calendar_coverage"
COVERAGE_UNDECLARED = "no_declared_calendar_coverage"
COVERAGE_INVALID = "invalid_calendar_date"

DEFAULT_CALENDAR_SOURCE = "fund_flow_monitor_declared_market_session_policy"
DEFAULT_CALENDAR_SOURCE_IDENTITY = "declared_market_session_dates_v1"
DEFAULT_MARKET_SESSION_CALENDAR_PATH = "config/market_session_calendar.json"

SOURCE_CLASSIFICATION_PROVIDER_DERIVED = "provider_derived"
SOURCE_CLASSIFICATION_EXCHANGE_PUBLISHED = "exchange_published"
SOURCE_CLASSIFICATION_PROJECT_REVIEWED = "project_reviewed_materialization"

ALIGNMENT_ALIGNED = "aligned"
ALIGNMENT_DIVERGENT = "divergent"
ALIGNMENT_COVERAGE_NOT_COMPARABLE = "coverage_not_comparable"
ALIGNMENT_SOURCE_UNRESOLVED = "source_unresolved"
ALIGNMENT_PROVIDER_UNIFIED = "provider_unified_domain_not_exchange_separated"


FORBIDDEN_MARKET_SESSION_POLICY_WORDS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "抄底",
    "逃顶",
    "推荐买",
    "推荐卖",
    "建议买",
    "建议卖",
    "建仓",
    "清仓",
    "未来会涨",
    "未来会跌",
    "适合配置",
    "应该调仓",
    "趋势确立",
    "反转确认",
    "强烈看好",
    "明确机会",
    "建议关注",
    "confidence",
    "probability",
    "score",
)


def _date_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _normalize_dates(values: Iterable[object] | None) -> list[str]:
    dates = sorted({_date_text(value) for value in (values or []) if _date_text(value)})
    return [item for item in dates if item]


def _raw_date_values(values: Iterable[object] | None) -> list[object]:
    return list(values or [])


def _invalid_date_values(values: Iterable[object] | None) -> list[str]:
    return [str(value) for value in _raw_date_values(values) if _date_text(value) is None]


def _duplicate_dates(values: Iterable[object] | None) -> list[str]:
    seen: set[str] = set()
    duplicate: set[str] = set()
    for value in _raw_date_values(values):
        text = _date_text(value)
        if not text:
            continue
        if text in seen:
            duplicate.add(text)
        seen.add(text)
    return sorted(duplicate)


def _source_reference_identity(policy: dict) -> str | None:
    value = policy.get("source_reference_identity")
    if value:
        return str(value)
    references = policy.get("source_references") or []
    if not isinstance(references, list):
        return None
    identity_parts = []
    for item in references:
        if not isinstance(item, dict):
            continue
        if bool(item.get("identity_defining", False)):
            identity_parts.append(
                {
                    "source_classification": item.get("source_classification"),
                    "source_name": item.get("source_name"),
                    "source_locator": item.get("source_locator"),
                    "source_identity": item.get("source_identity"),
                }
            )
    if not identity_parts:
        return None
    text = json.dumps(identity_parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _stable_policy_identity(policy: dict) -> str:
    payload = {
        "calendar_source": policy.get("calendar_source"),
        "calendar_source_identity": policy.get("calendar_source_identity"),
        "source_strategy": policy.get("source_strategy"),
        "source_classification": policy.get("source_classification"),
        "source_reference_identity": _source_reference_identity(policy),
        "market_scope": policy.get("market_scope"),
        "timezone": policy.get("timezone"),
        "calendar_semantics": policy.get("calendar_semantics"),
        "coverage_start": policy.get("coverage_start"),
        "coverage_end": policy.get("coverage_end"),
        "eligible_dates": _normalize_dates(policy.get("eligible_dates")),
        "closed_dates": _normalize_dates(policy.get("closed_dates")),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_market_session_policy_identity(policy: dict) -> str:
    return _stable_policy_identity(policy or {})


def _conservative_policy() -> dict:
    policy = {
        "calendar_source": DEFAULT_CALENDAR_SOURCE,
        "calendar_source_identity": DEFAULT_CALENDAR_SOURCE_IDENTITY,
        "source_strategy": "no_bundled_reference",
        "source_classification": "unresolved",
        "source_reference_identity": None,
        "market_scope": "unresolved_a_share_market_session_domain",
        "timezone": TIMEZONE,
        "calendar_semantics": "Dates explicitly declared as market-session eligible by this local policy.",
        "coverage_start": None,
        "coverage_end": None,
        "eligible_dates": [],
        "closed_dates": [],
        "special_open_dates": [],
        "closure_semantics": "Dates in closed_dates are explicitly non-eligible within declared coverage.",
        "coverage_semantics": "No bundled exchange-authoritative calendar. Dates outside explicit declared coverage are calendar_unverified.",
        "cross_exchange_alignment_state": ALIGNMENT_SOURCE_UNRESOLVED,
        "offline_deterministic": True,
        "network_used": False,
    }
    policy["calendar_policy_identity"] = _stable_policy_identity(policy)
    return policy


def get_conservative_market_session_policy() -> dict:
    return _conservative_policy()


def get_default_market_session_policy() -> dict:
    """Return the bundled offline market-session policy when available.

    The bundled reference is provider-derived and non-exchange-authoritative.
    If it is absent, the function falls back to the conservative policy where
    dates remain calendar-unverified unless a caller supplies explicit coverage.
    """

    try:
        return load_market_session_policy_from_reference(DEFAULT_MARKET_SESSION_CALENDAR_PATH)
    except FileNotFoundError:
        return _conservative_policy()


def build_declared_market_session_policy(
    *,
    eligible_dates: Iterable[object],
    coverage_start: object,
    coverage_end: object,
    closed_dates: Iterable[object] | None = None,
    calendar_source: str = DEFAULT_CALENDAR_SOURCE,
    calendar_source_identity: str = DEFAULT_CALENDAR_SOURCE_IDENTITY,
) -> dict:
    start = _date_text(coverage_start)
    end = _date_text(coverage_end)
    policy = {
        **_conservative_policy(),
        "calendar_source": calendar_source,
        "calendar_source_identity": calendar_source_identity,
        "source_strategy": "caller_declared_policy",
        "source_classification": SOURCE_CLASSIFICATION_PROJECT_REVIEWED,
        "source_reference_identity": f"{calendar_source}:{calendar_source_identity}",
        "market_scope": "caller_declared_market_session_domain",
        "coverage_start": start,
        "coverage_end": end,
        "eligible_dates": _normalize_dates(eligible_dates),
        "closed_dates": _normalize_dates(closed_dates),
        "coverage_semantics": "Within the declared coverage range, only eligible_dates are market-session eligible; closed_dates are explicitly non-eligible.",
    }
    policy["calendar_policy_identity"] = _stable_policy_identity(policy)
    return policy


def evaluate_market_session_date(calendar_date: object, policy: dict | None = None) -> dict:
    policy = dict(policy or get_default_market_session_policy())
    date_text = _date_text(calendar_date)
    source = str(policy.get("calendar_source") or DEFAULT_CALENDAR_SOURCE)
    source_identity = str(policy.get("calendar_source_identity") or DEFAULT_CALENDAR_SOURCE_IDENTITY)
    eligible_dates = set(_normalize_dates(policy.get("eligible_dates")))
    closed_dates = set(_normalize_dates(policy.get("closed_dates")))
    start = _date_text(policy.get("coverage_start"))
    end = _date_text(policy.get("coverage_end"))
    policy_identity = _stable_policy_identity(policy)

    base = {
        "calendar_date": date_text,
        "calendar_source": source,
        "calendar_source_identity": source_identity,
        "calendar_policy_identity": policy_identity,
        "market_scope": policy.get("market_scope"),
        "source_strategy": policy.get("source_strategy"),
        "source_classification": policy.get("source_classification"),
        "cross_exchange_alignment_state": policy.get("cross_exchange_alignment_state"),
        "calendar_coverage_start": start,
        "calendar_coverage_end": end,
        "calendar_coverage_state": COVERAGE_UNDECLARED,
        "market_session_date_state": STATE_UNVERIFIED,
        "is_market_session_date_eligible": False,
        "decision_reason": "No declared market-session date coverage is available for this calendar date.",
        "network_used": False,
    }
    if date_text is None:
        return {
            **base,
            "calendar_coverage_state": COVERAGE_INVALID,
            "decision_reason": "Calendar date is missing or invalid.",
        }

    in_declared_range = bool(start and end and start <= date_text <= end)
    if date_text in eligible_dates:
        return {
            **base,
            "calendar_coverage_state": COVERAGE_DECLARED,
            "market_session_date_state": STATE_ELIGIBLE,
            "is_market_session_date_eligible": True,
            "decision_reason": "Calendar date is explicitly declared as market-session eligible by the local offline policy.",
        }
    if date_text in closed_dates:
        return {
            **base,
            "calendar_coverage_state": COVERAGE_DECLARED,
            "market_session_date_state": STATE_INELIGIBLE,
            "decision_reason": "Calendar date is explicitly declared closed or non-eligible by the local offline policy.",
        }
    if in_declared_range:
        return {
            **base,
            "calendar_coverage_state": COVERAGE_DECLARED,
            "market_session_date_state": STATE_INELIGIBLE,
            "decision_reason": "Calendar date falls inside declared coverage but is not declared market-session eligible.",
        }
    if start and end:
        return {
            **base,
            "calendar_coverage_state": COVERAGE_OUTSIDE,
            "decision_reason": "Calendar date is outside the supported declared calendar coverage range.",
        }
    return base


def validate_market_session_policy_text(text: str) -> list[str]:
    value = str(text or "")
    return [word for word in FORBIDDEN_MARKET_SESSION_POLICY_WORDS if word in value]


def validate_market_session_reference(reference: dict) -> dict:
    data = dict(reference or {})
    errors: list[str] = []
    warnings: list[str] = []
    eligible = _normalize_dates(data.get("eligible_session_dates") or data.get("eligible_dates"))
    closed = _normalize_dates(data.get("explicit_closed_dates") or data.get("closed_dates"))
    invalid = _invalid_date_values(data.get("eligible_session_dates") or data.get("eligible_dates"))
    invalid.extend(_invalid_date_values(data.get("explicit_closed_dates") or data.get("closed_dates")))
    duplicates = _duplicate_dates(data.get("eligible_session_dates") or data.get("eligible_dates"))
    duplicates.extend(_duplicate_dates(data.get("explicit_closed_dates") or data.get("closed_dates")))
    start = _date_text(data.get("coverage_start"))
    end = _date_text(data.get("coverage_end"))
    if data.get("schema_version") != "market_session_calendar_v1":
        errors.append("schema_version must be market_session_calendar_v1.")
    if invalid:
        errors.append(f"Invalid date values: {sorted(set(invalid))}")
    if duplicates:
        warnings.append(f"Duplicate date values were normalized: {sorted(set(duplicates))}")
    if not start or not end:
        errors.append("coverage_start and coverage_end are required ISO dates.")
    elif start > end:
        errors.append("coverage_start must be <= coverage_end.")
    outside = [item for item in eligible + closed if start and end and not (start <= item <= end)]
    if outside:
        errors.append(f"Dates outside coverage range: {outside}")
    overlap = sorted(set(eligible).intersection(closed))
    if overlap:
        errors.append(f"Dates cannot be both eligible and closed: {overlap}")
    if not data.get("market_scope"):
        errors.append("market_scope is required.")
    if data.get("timezone") != TIMEZONE:
        errors.append(f"timezone must be {TIMEZONE}.")
    if not data.get("source_classification"):
        errors.append("source_classification is required.")
    if not data.get("calendar_source_identity"):
        errors.append("calendar_source_identity is required.")
    if not eligible:
        warnings.append("No eligible_session_dates are declared.")
    return {
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "eligible_dates": eligible,
        "closed_dates": closed,
        "coverage_start": start,
        "coverage_end": end,
    }


def build_policy_from_market_session_reference(reference: dict) -> dict:
    validation = validate_market_session_reference(reference)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))
    data = dict(reference or {})
    policy = {
        "calendar_source": str(data.get("calendar_source") or data.get("calendar_name") or "market_session_calendar_reference"),
        "calendar_source_identity": str(data.get("calendar_source_identity")),
        "source_strategy": str(data.get("source_strategy") or "provider_derived_materialization"),
        "source_classification": str(data.get("source_classification")),
        "source_reference_identity": data.get("source_reference_identity"),
        "source_references": data.get("source_references") or [],
        "market_scope": str(data.get("market_scope")),
        "timezone": str(data.get("timezone") or TIMEZONE),
        "calendar_semantics": str(data.get("calendar_semantics") or ""),
        "coverage_start": validation["coverage_start"],
        "coverage_end": validation["coverage_end"],
        "eligible_dates": validation["eligible_dates"],
        "closed_dates": validation["closed_dates"],
        "special_open_dates": [],
        "closure_semantics": str(data.get("closure_semantics") or "Dates absent from eligible_dates inside coverage are not eligible."),
        "coverage_semantics": str(data.get("coverage_semantics") or "Within coverage, only eligible_session_dates are market-session eligible."),
        "cross_exchange_alignment_state": (data.get("exchange_reconciliation") or {}).get("cross_exchange_alignment_state"),
        "exchange_reconciliation": data.get("exchange_reconciliation") or {},
        "offline_deterministic": True,
        "network_used": False,
    }
    policy["calendar_policy_identity"] = _stable_policy_identity(policy)
    return policy


def load_market_session_reference(path: str | Path = DEFAULT_MARKET_SESSION_CALENDAR_PATH) -> dict:
    ref_path = Path(path)
    if not ref_path.exists():
        raise FileNotFoundError(str(ref_path))
    return json.loads(ref_path.read_text(encoding="utf-8"))


def load_market_session_policy_from_reference(path: str | Path = DEFAULT_MARKET_SESSION_CALENDAR_PATH) -> dict:
    return build_policy_from_market_session_reference(load_market_session_reference(path))


def reconcile_exchange_session_domains(
    sse_eligible_dates: Iterable[object],
    szse_eligible_dates: Iterable[object],
    *,
    coverage_start: object | None = None,
    coverage_end: object | None = None,
) -> dict:
    sse_dates = set(_normalize_dates(sse_eligible_dates))
    szse_dates = set(_normalize_dates(szse_eligible_dates))
    start = _date_text(coverage_start) or (max(min(sse_dates), min(szse_dates)) if sse_dates and szse_dates else None)
    end = _date_text(coverage_end) or (min(max(sse_dates), max(szse_dates)) if sse_dates and szse_dates else None)
    if not start or not end or start > end:
        return {
            "cross_exchange_alignment_state": ALIGNMENT_COVERAGE_NOT_COMPARABLE,
            "overlapping_coverage_start": start,
            "overlapping_coverage_end": end,
            "sse_eligible_date_count": len(sse_dates),
            "szse_eligible_date_count": len(szse_dates),
            "common_eligible_date_count": 0,
            "sse_only_date_count": 0,
            "szse_only_date_count": 0,
            "sse_only_dates": [],
            "szse_only_dates": [],
            "common_eligible_dates": [],
        }
    sse_in_range = {item for item in sse_dates if start <= item <= end}
    szse_in_range = {item for item in szse_dates if start <= item <= end}
    common = sorted(sse_in_range.intersection(szse_in_range))
    sse_only = sorted(sse_in_range - szse_in_range)
    szse_only = sorted(szse_in_range - sse_in_range)
    state = ALIGNMENT_ALIGNED if not sse_only and not szse_only else ALIGNMENT_DIVERGENT
    return {
        "cross_exchange_alignment_state": state,
        "overlapping_coverage_start": start,
        "overlapping_coverage_end": end,
        "sse_eligible_date_count": len(sse_in_range),
        "szse_eligible_date_count": len(szse_in_range),
        "common_eligible_date_count": len(common),
        "sse_only_date_count": len(sse_only),
        "szse_only_date_count": len(szse_only),
        "sse_only_dates": sse_only,
        "szse_only_dates": szse_only,
        "common_eligible_dates": common,
    }
