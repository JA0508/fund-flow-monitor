from pathlib import Path


REFRESH_INTERVAL_SECONDS = 30
DEFAULT_SECTOR_TYPE = "行业资金流"
DEFAULT_TOP_IN = 10
DEFAULT_TOP_OUT = 15
DATA_SOURCE = "AKShare / Eastmoney"
TIMEZONE = "Asia/Shanghai"
DATA_DIR = Path("data/ticks")

SECTOR_TYPES = ("行业资金流", "概念资金流")
TRADING_STATUSES = {"pre_open", "trading_morning", "trading_afternoon"}
FETCH_ALLOWED_STATUSES = TRADING_STATUSES | {"lunch_break"}

