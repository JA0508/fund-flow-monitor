from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
import pytz

from src.config import TIMEZONE


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_china_now():
    return pd.Timestamp.now(tz=pytz.timezone(TIMEZONE)).to_pydatetime()


def safe_to_float(value: Any) -> float:
    """Convert mixed numeric strings, including Chinese units, to float."""
    if value is None:
        return math.nan
    if isinstance(value, float):
        return value if not math.isnan(value) else math.nan
    if isinstance(value, int):
        return float(value)
    if pd.isna(value):
        return math.nan

    text = str(value).strip()
    if not text or text in {"-", "--", "None", "nan", "NaN", "null"}:
        return math.nan

    multiplier = 1.0
    text = (
        text.replace(",", "")
        .replace("，", "")
        .replace(" ", "")
        .replace("+", "")
        .replace("%", "")
        .replace("人民币", "")
        .replace("元", "")
    )

    if text.endswith("万亿"):
        multiplier = 1_000_000_000_000.0
        text = text[:-2]
    elif text.endswith("亿"):
        multiplier = 100_000_000.0
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 10_000.0
        text = text[:-1]

    try:
        return float(text) * multiplier
    except (TypeError, ValueError):
        return math.nan


def format_billion(value: Any) -> str:
    number = safe_to_float(value)
    if math.isnan(number):
        return "--"
    return f"{number:.1f}亿"

