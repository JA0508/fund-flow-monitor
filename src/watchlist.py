from __future__ import annotations

import json
import os
import tempfile
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


def _default_watchlist(reason: str) -> dict:
    return {
        **DEFAULT_WATCHLIST,
        "themes": list(DEFAULT_WATCHLIST["themes"]),
        "_load_warning": f"{reason}，当前显示默认关注主题，并非已恢复个人选择。",
    }


def load_watchlist(path: str = "config/watchlist.json") -> dict:
    target = Path(path)
    if not target.exists():
        return _default_watchlist("关注配置不存在")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return _default_watchlist("关注配置读取失败")
    if not isinstance(data, dict):
        return _default_watchlist("关注配置格式无效")
    themes = data.get("themes")
    if not isinstance(themes, list) or any(not isinstance(theme, str) for theme in themes):
        return _default_watchlist("关注主题列表格式无效")
    return {
        "watchlist_name": str(data.get("watchlist_name") or DEFAULT_WATCHLIST["watchlist_name"]),
        "themes": [str(theme) for theme in themes if str(theme).strip()],
    }


def get_watchlist_themes(watchlist: dict) -> list[str]:
    themes = watchlist.get("themes", []) if isinstance(watchlist, dict) else []
    return [str(theme) for theme in themes if str(theme).strip()]


def save_personal_watchlist(path: Path, themes: list[str], allowed_themes: list[str]) -> None:
    if not isinstance(themes, list) or any(
        not isinstance(theme, str) or theme not in allowed_themes for theme in themes
    ):
        raise ValueError("关注主题必须来自当前主题分类。")
    payload = {"watchlist_name": "个人关注主题", "themes": list(dict.fromkeys(themes))}
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # Same-directory replacement preserves the previous file on write failure.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def filter_watchlist_theme_df(theme_df: pd.DataFrame, themes: list[str]) -> pd.DataFrame:
    if theme_df is None or theme_df.empty or not themes:
        return pd.DataFrame()
    name_col = "theme_name" if "theme_name" in theme_df.columns else "sector_name"
    return theme_df[theme_df[name_col].isin(themes)].copy()

