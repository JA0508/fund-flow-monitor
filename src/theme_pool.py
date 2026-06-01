from __future__ import annotations

from typing import Literal

import pandas as pd


ThemeMode = Literal["representative", "breadth"]


THEME_DEFINITIONS = {
    "半导体/芯片链": {
        "primary_sectors": ["半导体", "集成电路", "国产芯片", "芯片概念"],
        "related_sectors": [
            "半导体设备",
            "集成电路制造",
            "集成电路封测",
            "PCB",
            "印制电路板",
            "存储芯片",
            "元件",
            "电子",
            "消费电子",
            "光学光电子",
            "电子化学品",
            "模拟芯片设计",
        ],
    },
    "AI算力/TMT": {
        "primary_sectors": ["计算机", "通信设备", "通信", "传媒"],
        "related_sectors": [
            "软件开发",
            "IT服务Ⅱ",
            "IT服务Ⅲ",
            "CPO",
            "光模块",
            "算力",
            "AI应用",
            "横向通用软件",
            "计算机设备",
            "通信服务",
            "通信网络设备及器件",
        ],
    },
    "新能源链": {
        "primary_sectors": ["电力设备", "电池", "光伏设备", "储能"],
        "related_sectors": [
            "锂电池",
            "锂矿",
            "电池化学品",
            "蓄电池及其他电池",
            "光伏",
            "光伏发电",
            "光伏主材",
            "光伏辅材",
            "光伏电池组件",
            "输变电设备",
            "电网设备",
        ],
    },
    "红利防御": {
        "primary_sectors": ["银行", "电力", "公用事业", "煤炭"],
        "related_sectors": [
            "火力发电",
            "水力发电",
            "煤炭开采",
            "电信运营商",
            "运营商",
        ],
    },
    "消费": {
        "primary_sectors": ["食品饮料", "白酒", "家电", "旅游酒店"],
        "related_sectors": [
            "白色家电",
            "小家电",
            "黑色家电",
            "家电零部件",
            "零售",
            "免税",
            "消费电子",
        ],
    },
    "医药": {
        "primary_sectors": ["医药生物", "创新药", "中药", "医疗器械"],
        "related_sectors": ["医疗服务", "化学制药", "生物制品", "中药Ⅱ", "中药Ⅲ"],
    },
    "军工": {
        "primary_sectors": ["国防军工", "军工", "航空装备"],
        "related_sectors": ["航空装备Ⅱ", "航空装备Ⅲ", "商业航天", "低空经济", "航天装备"],
    },
    "证券金融": {
        "primary_sectors": ["证券", "保险", "银行"],
        "related_sectors": [
            "证券Ⅱ",
            "证券Ⅲ",
            "保险Ⅱ",
            "保险Ⅲ",
            "互联网金融",
            "资本市场",
            "多元金融",
        ],
    },
}

THEME_MODE_LABELS = {
    "representative": "代表口径",
    "breadth": "观察强度",
}


def _matches(text: str, keyword: str) -> bool:
    return keyword == text or keyword in text


def _match_theme(sector_name: str) -> tuple[str | None, str | None]:
    if not sector_name:
        return None, None
    text = str(sector_name).strip()
    for theme_name, definition in THEME_DEFINITIONS.items():
        for keyword in definition["primary_sectors"]:
            if keyword == text:
                return theme_name, "primary"
        for keyword in definition["related_sectors"]:
            if keyword == text:
                return theme_name, "related"
        for keyword in definition["primary_sectors"]:
            if _matches(text, keyword):
                return theme_name, "primary"
        for keyword in definition["related_sectors"]:
            if _matches(text, keyword):
                return theme_name, "related"
    return None, None


def map_to_theme(sector_name: str) -> str | None:
    theme_name, _ = _match_theme(sector_name)
    return theme_name


def _normalize_theme_mode(theme_mode: str) -> ThemeMode:
    return "breadth" if theme_mode == "breadth" else "representative"


def _sum_optional(group: pd.DataFrame, column: str) -> float:
    if column not in group.columns:
        return 0.0
    return pd.to_numeric(group[column], errors="coerce").sum()


def _mean_optional(group: pd.DataFrame, column: str) -> float:
    if column not in group.columns:
        return float("nan")
    return pd.to_numeric(group[column], errors="coerce").mean()


def _leading_stock_for_group(group: pd.DataFrame) -> str | None:
    if group.empty or "leading_stock" not in group.columns:
        return None
    idx = group["main_net_inflow_billion"].abs().idxmax()
    value = group.loc[idx, "leading_stock"]
    return None if pd.isna(value) else str(value)


def _sectors_for_group(group: pd.DataFrame) -> list[str]:
    return group["sector_name"].dropna().astype(str).drop_duplicates().tolist()


def _join_sectors(group: pd.DataFrame) -> str:
    return "，".join(_sectors_for_group(group))


def _annotate_matches(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    matches = work["sector_name"].map(_match_theme)
    work["theme_name"] = matches.map(lambda item: item[0])
    work["theme_match_type"] = matches.map(lambda item: item[1])
    work["main_net_inflow_billion"] = pd.to_numeric(
        work["main_net_inflow_billion"], errors="coerce"
    )
    return work.dropna(subset=["theme_name", "main_net_inflow_billion"])


def _select_used_group(theme_group: pd.DataFrame, theme_mode: ThemeMode) -> pd.DataFrame:
    if theme_mode == "breadth":
        return theme_group
    primary = theme_group[theme_group["theme_match_type"].eq("primary")]
    if not primary.empty:
        return primary
    return theme_group[theme_group["theme_match_type"].eq("related")]


def _build_theme_row(
    theme_name: str,
    source_group: pd.DataFrame,
    used_group: pd.DataFrame,
    theme_mode: ThemeMode,
) -> dict:
    first = source_group.iloc[0]
    inflow = used_group["main_net_inflow_billion"].sum()
    source_sectors = _join_sectors(source_group)
    used_sectors = _join_sectors(used_group)
    label = THEME_MODE_LABELS[theme_mode]
    return {
        "trade_date": first.get("trade_date"),
        "captured_at": first.get("captured_at"),
        "captured_time": first.get("captured_time"),
        "sector_type": first.get("sector_type"),
        "sector_code": f"THEME:{theme_name}",
        "sector_name": theme_name,
        "theme_name": theme_name,
        "change_pct": _mean_optional(used_group, "change_pct"),
        "main_net_inflow_yuan": inflow * 100_000_000,
        "main_net_inflow_billion": inflow,
        "main_net_ratio": _mean_optional(used_group, "main_net_ratio"),
        "super_large_net_inflow_yuan": _sum_optional(used_group, "super_large_net_inflow_yuan"),
        "large_net_inflow_yuan": _sum_optional(used_group, "large_net_inflow_yuan"),
        "medium_net_inflow_yuan": _sum_optional(used_group, "medium_net_inflow_yuan"),
        "small_net_inflow_yuan": _sum_optional(used_group, "small_net_inflow_yuan"),
        "leading_stock": _leading_stock_for_group(used_group),
        "source": first.get("source"),
        "source_sectors": source_sectors,
        "used_sectors": used_sectors,
        "source_sector_count": len(_sectors_for_group(source_group)),
        "used_sector_count": len(_sectors_for_group(used_group)),
        "aggregation_mode": theme_mode,
        "theme_value_label": label,
    }


def build_theme_snapshot(
    latest_df: pd.DataFrame,
    theme_mode: str = "representative",
) -> pd.DataFrame:
    if latest_df is None or latest_df.empty:
        return pd.DataFrame()

    mode = _normalize_theme_mode(theme_mode)
    df = _annotate_matches(latest_df)
    if df.empty:
        return pd.DataFrame()

    rows = []
    for theme_name, source_group in df.groupby("theme_name", sort=False):
        used_group = _select_used_group(source_group, mode)
        if not used_group.empty:
            rows.append(_build_theme_row(theme_name, source_group, used_group, mode))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("main_net_inflow_billion", ascending=False).reset_index(drop=True)


def apply_theme_pool_to_ticks(
    ticks_df: pd.DataFrame,
    theme_mode: str = "representative",
) -> pd.DataFrame:
    if ticks_df is None or ticks_df.empty:
        return pd.DataFrame()

    mode = _normalize_theme_mode(theme_mode)
    df = _annotate_matches(ticks_df)
    if df.empty:
        return pd.DataFrame()

    group_keys = ["trade_date", "captured_at", "captured_time", "sector_type", "theme_name"]
    rows = []
    for keys, source_group in df.groupby(group_keys, dropna=False, sort=False):
        theme_name = keys[-1]
        used_group = _select_used_group(source_group, mode)
        if not used_group.empty:
            rows.append(_build_theme_row(theme_name, source_group, used_group, mode))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["captured_at", "main_net_inflow_billion"]).reset_index(drop=True)
