from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


DEFAULT_WATCHLIST = {
    "watchlist_name": "默认关注主题",
    "themes": [
        "半导体/芯片链",
        "AI算力/TMT",
        "新能源链",
        "红利防御",
        "医药",
        "证券金融",
    ],
}


def load_watchlist(path: str = "config/watchlist.json") -> dict:
    target = Path(path)
    if not target.exists():
        return DEFAULT_WATCHLIST.copy()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_WATCHLIST.copy()
    if not isinstance(data, dict):
        return DEFAULT_WATCHLIST.copy()
    themes = data.get("themes")
    if not isinstance(themes, list):
        return DEFAULT_WATCHLIST.copy()
    return {
        "watchlist_name": str(data.get("watchlist_name") or DEFAULT_WATCHLIST["watchlist_name"]),
        "themes": [str(theme) for theme in themes if str(theme).strip()],
    }


def get_watchlist_themes(watchlist: dict) -> list[str]:
    themes = watchlist.get("themes", []) if isinstance(watchlist, dict) else []
    return [str(theme) for theme in themes if str(theme).strip()]


def filter_watchlist_theme_df(theme_df: pd.DataFrame, themes: list[str]) -> pd.DataFrame:
    if theme_df is None or theme_df.empty or not themes:
        return pd.DataFrame()
    name_col = "theme_name" if "theme_name" in theme_df.columns else "sector_name"
    return theme_df[theme_df[name_col].isin(themes)].copy()

