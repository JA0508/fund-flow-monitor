from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Iterable


STATE_ELIGIBLE = "eligible_market_session_date"
STATE_INELIGIBLE = "market_session_date_ineligible"
STATE_UNVERIFIED = "market_calendar_unverified"

COVERAGE_DECLARED = "declared_calendar_coverage"
COVERAGE_OUTSIDE = "outside_supported_calendar_coverage"
COVERAGE_UNDECLARED = "no_declared_calendar_coverage"
COVERAGE_INVALID = "invalid_calendar_date"

DEFAULT_CALENDAR_SOURCE = "fund_flow_monitor_declared_market_session_policy"
DEFAULT_CALENDAR_SOURCE_IDENTITY = "declared_market_session_dates_v1"


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


def _stable_policy_identity(policy: dict) -> str:
    payload = {
        "calendar_source": policy.get("calendar_source"),
        "calendar_source_identity": policy.get("calendar_source_identity"),
        "coverage_start": policy.get("coverage_start"),
        "coverage_end": policy.get("coverage_end"),
        "eligible_dates": _normalize_dates(policy.get("eligible_dates")),
        "closed_dates": _normalize_dates(policy.get("closed_dates")),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def get_default_market_session_policy() -> dict:
    """Return the conservative offline market-session date policy.

    The project does not bundle an exchange-authoritative trading calendar.
    A REAL date is eligible only when a caller supplies a declared date policy
    with explicit coverage. This prevents clock-window membership from becoming
    market-session-date proof.
    """

    return {
        "calendar_source": DEFAULT_CALENDAR_SOURCE,
        "calendar_source_identity": DEFAULT_CALENDAR_SOURCE_IDENTITY,
        "calendar_semantics": "Dates explicitly declared as market-session eligible by this local policy.",
        "coverage_start": None,
        "coverage_end": None,
        "eligible_dates": [],
        "closed_dates": [],
        "special_open_dates": [],
        "closure_semantics": "Dates in closed_dates are explicitly non-eligible within declared coverage.",
        "coverage_semantics": "No bundled exchange-authoritative calendar. Dates outside explicit declared coverage are calendar_unverified.",
        "offline_deterministic": True,
        "network_used": False,
    }


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
    return {
        **get_default_market_session_policy(),
        "calendar_source": calendar_source,
        "calendar_source_identity": calendar_source_identity,
        "coverage_start": start,
        "coverage_end": end,
        "eligible_dates": _normalize_dates(eligible_dates),
        "closed_dates": _normalize_dates(closed_dates),
        "coverage_semantics": "Within the declared coverage range, only eligible_dates are market-session eligible; closed_dates are explicitly non-eligible.",
    }


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
