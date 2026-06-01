from __future__ import annotations

from datetime import datetime, time

import pytz

from src.config import TIMEZONE


def _normalize_now(now: datetime | None) -> datetime:
    tz = pytz.timezone(TIMEZONE)
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return tz.localize(now)
    return now.astimezone(tz)


def get_market_status(now: datetime | None = None) -> str:
    current = _normalize_now(now)
    if current.weekday() >= 5:
        return "weekend"

    t = current.time()
    if time(9, 15) <= t < time(9, 30):
        return "pre_open"
    if time(9, 30) <= t < time(11, 30):
        return "trading_morning"
    if time(11, 30) <= t < time(13, 0):
        return "lunch_break"
    if time(13, 0) <= t < time(15, 0):
        return "trading_afternoon"
    return "closed"

