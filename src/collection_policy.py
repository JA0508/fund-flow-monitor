from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.config import TIMEZONE
from src.market_session_policy import evaluate_market_session_date, get_default_market_session_policy


TRUE_VALUES = {"1", "true", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "n", "off"}


def get_default_collection_policy() -> dict:
    return {
        "enabled": True,
        "timezone": TIMEZONE,
        "min_interval_seconds": 300,
        "max_attempts_per_session": 12,
        "market_session_policy": get_default_market_session_policy(),
        "sessions": [
            {"name": "morning_session", "label": "上午交易观察窗口", "start": "09:30", "end": "11:30"},
            {"name": "afternoon_session", "label": "下午交易观察窗口", "start": "13:00", "end": "15:00"},
        ],
    }


def parse_policy_time(value: str | time) -> time:
    if isinstance(value, time):
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError("policy time 不能为空。")
    parts = text.split(":")
    if len(parts) == 2:
        text = f"{text}:00"
    return time.fromisoformat(text)


def _get_timezone(policy: dict | None = None) -> ZoneInfo:
    name = (policy or {}).get("timezone") or TIMEZONE
    return ZoneInfo(str(name))


def _now(policy: dict | None = None, now: datetime | None = None) -> datetime:
    tz = _get_timezone(policy)
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def _parse_datetime(value: str | datetime | None, policy: dict | None = None) -> datetime | None:
    if value is None:
        return None
    tz = _get_timezone(policy)
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _session_bounds(session: dict, current: datetime, policy: dict) -> tuple[datetime, datetime]:
    start = parse_policy_time(session.get("start"))
    end = parse_policy_time(session.get("end"))
    start_dt = current.replace(hour=start.hour, minute=start.minute, second=start.second, microsecond=0)
    end_dt = current.replace(hour=end.hour, minute=end.minute, second=end.second, microsecond=0)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
        if current < start_dt:
            start_dt -= timedelta(days=1)
            end_dt -= timedelta(days=1)
    return start_dt, end_dt


def find_active_session(policy: dict | None = None, now: datetime | None = None) -> dict | None:
    policy = policy or get_default_collection_policy()
    current = _now(policy, now)
    for session in policy.get("sessions", []):
        start_dt, end_dt = _session_bounds(session, current, policy)
        if start_dt <= current <= end_dt:
            result = dict(session)
            result["start_at"] = start_dt.isoformat()
            result["end_at"] = end_dt.isoformat()
            return result
    return None


def _seconds_until_next_session(policy: dict, current: datetime) -> int | None:
    candidates: list[datetime] = []
    for session in policy.get("sessions", []):
        start = parse_policy_time(session.get("start"))
        start_today = current.replace(hour=start.hour, minute=start.minute, second=start.second, microsecond=0)
        if start_today > current:
            candidates.append(start_today)
        candidates.append(start_today + timedelta(days=1))
    if not candidates:
        return None
    return max(0, int((min(candidates) - current).total_seconds()))


def decide_collection_eligibility(
    policy: dict | None = None,
    now: datetime | None = None,
    latest_success_at: str | datetime | None = None,
    attempts_in_active_session: int = 0,
) -> dict:
    policy = policy or get_default_collection_policy()
    current = _now(policy, now)
    latest_success = _parse_datetime(latest_success_at, policy)
    attempts = max(0, int(attempts_in_active_session or 0))
    min_interval = max(0, int(policy.get("min_interval_seconds", 0) or 0))
    max_attempts = max(1, int(policy.get("max_attempts_per_session", 1) or 1))

    base = {
        "current_time": current.isoformat(),
        "timezone": str(policy.get("timezone") or TIMEZONE),
        "calendar_date": current.date().isoformat(),
        "market_session_date_state": None,
        "is_market_session_date_eligible": None,
        "calendar_source": None,
        "calendar_source_identity": None,
        "calendar_policy_identity": None,
        "calendar_coverage_state": None,
        "market_session_date_reason": None,
        "active_session_name": None,
        "latest_success_at": latest_success.isoformat() if latest_success else None,
        "seconds_since_latest_success": None,
        "seconds_until_next_eligible": None,
        "seconds_until_next_clock_session": None,
        "seconds_until_next_eligible_semantics": "not_evaluated",
        "attempts_in_active_session": attempts,
        "min_interval_seconds": min_interval,
        "max_attempts_per_session": max_attempts,
    }

    if not bool(policy.get("enabled", True)):
        return {
            **base,
            "eligible": False,
            "policy_status": "disabled",
            "policy_reason": "采集策略已禁用；本地真实数据采集不会启动。",
        }

    date_decision = evaluate_market_session_date(
        current.date(),
        policy.get("market_session_policy"),
    )
    base.update(
        {
            "market_session_date_state": date_decision.get("market_session_date_state"),
            "is_market_session_date_eligible": bool(date_decision.get("is_market_session_date_eligible")),
            "calendar_source": date_decision.get("calendar_source"),
            "calendar_source_identity": date_decision.get("calendar_source_identity"),
            "calendar_policy_identity": date_decision.get("calendar_policy_identity"),
            "calendar_coverage_state": date_decision.get("calendar_coverage_state"),
            "market_session_date_reason": date_decision.get("decision_reason"),
        }
    )
    if not date_decision.get("is_market_session_date_eligible"):
        seconds = _seconds_until_next_session(policy, current)
        return {
            **base,
            "eligible": False,
            "policy_status": date_decision.get("market_session_date_state") or "market_calendar_unverified",
            "policy_reason": date_decision.get("decision_reason") or "当前日期未通过 market-session date eligibility。",
            "seconds_until_next_clock_session": seconds,
            "seconds_until_next_eligible_semantics": "not_reported_without_market_session_date_eligibility",
        }

    active_session = find_active_session(policy, current)
    if active_session is None:
        seconds = _seconds_until_next_session(policy, current)
        return {
            **base,
            "eligible": False,
            "policy_status": "outside_session",
            "policy_reason": "当前时间不在预设交易观察窗口内。",
            "seconds_until_next_eligible": None,
            "seconds_until_next_clock_session": seconds,
            "seconds_until_next_eligible_semantics": "clock_session_boundary_only",
        }

    base["active_session_name"] = active_session.get("name")

    if attempts >= max_attempts:
        return {
            **base,
            "eligible": False,
            "policy_status": "max_attempts_reached",
            "policy_reason": "当前观察窗口内已达到最大尝试次数。",
        }

    if latest_success is not None:
        seconds_since = int((current - latest_success).total_seconds())
        base["seconds_since_latest_success"] = seconds_since
        if 0 <= seconds_since < min_interval:
            return {
                **base,
                "eligible": False,
                "policy_status": "too_soon_since_success",
                "policy_reason": "距离上次成功采集时间过短，暂不重复写入真实缓存。",
                "seconds_until_next_eligible": max(0, min_interval - seconds_since),
                "seconds_until_next_eligible_semantics": "min_interval_with_market_session_date_and_active_clock_session",
            }

    return {
        **base,
        "eligible": True,
        "policy_status": "eligible",
        "policy_reason": "当前处于采集观察窗口，且未触发最小间隔或次数上限。",
        "seconds_until_next_eligible_semantics": "already_eligible",
    }


def validate_collection_policy_text(text: str) -> list[str]:
    forbidden = [
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
    ]
    return sorted({word for word in forbidden if word in str(text or "")})
