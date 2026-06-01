from datetime import datetime

import pytz

from src.market_time import get_market_status


TZ = pytz.timezone("Asia/Shanghai")


def at(hour, minute, day=29):
    return TZ.localize(datetime(2026, 5, day, hour, minute))


def test_pre_open():
    assert get_market_status(at(9, 20)) == "pre_open"


def test_trading_morning():
    assert get_market_status(at(10, 0)) == "trading_morning"


def test_lunch_break():
    assert get_market_status(at(12, 0)) == "lunch_break"


def test_trading_afternoon():
    assert get_market_status(at(14, 0)) == "trading_afternoon"


def test_closed():
    assert get_market_status(at(15, 30)) == "closed"


def test_weekend():
    assert get_market_status(TZ.localize(datetime(2026, 5, 30, 10, 0))) == "weekend"

