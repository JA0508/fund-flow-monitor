from __future__ import annotations

from typing import Literal

import pandas as pd

from src.theme_taxonomy import load_theme_taxonomy, taxonomy_to_theme_definitions


ThemeMode = Literal["strict_representative", "representative", "breadth"]


FALLBACK_THEME_DEFINITIONS = {
    "半导体/芯片链": {
        "primary_sectors": ["半导体"],
        "related_sectors": [
            "半导体材料",
            "半导体设备",
            "集成电路制造",
            "集成电路封测",
            "模拟芯片设计",
            "PCB",
            "印制电路板",
            "存储芯片",
            "元件",
            "电子",
            "消费电子",
            "光学光电子",
            "电子化学品",
        ],
    },
    "AI算力/TMT": {
        "primary_sectors": ["计算机", "通信", "通信设备", "传媒"],
        "related_sectors": [
            "软件开发",
            "IT服务Ⅱ",
            "IT服务Ⅲ",
            "横向通用软件",
            "计算机设备",
            "其他计算机设备",
            "通信服务",
            "通信网络设备及器件",
            "通信工程及服务",
            "通信终端及配件",
            "CPO",
            "光模块",
            "算力",
            "AI应用",
        ],
    },
    "新能源链": {
        "primary_sectors": ["电力设备", "电池", "光伏设备", "储能"],
        "related_sectors": [
            "锂电池",
            "锂矿",
            "电池化学品",
            "蓄电池及其他电池",
            "燃料电池",
            "光伏发电",
            "光伏主材",
            "光伏辅材",
            "光伏电池组件",
            "输变电设备",
            "电网设备",
            "综合电力设备商",
        ],
    },
    "红利防御": {
        "primary_sectors": ["银行", "电力", "公用事业", "煤炭"],
        "related_sectors": [
            "银行Ⅱ",
            "股份制银行Ⅲ",
            "国有大型银行Ⅲ",
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
            "一般零售",
            "多业态零售",
            "商贸零售",
            "旅游零售",
            "消费电子",
        ],
    },
    "医药": {
        "primary_sectors": ["医药生物", "中药", "医疗器械"],
        "related_sectors": ["中药Ⅱ", "中药Ⅲ", "医疗服务", "化学制药", "生物制品", "其他生物制品", "创新药"],
    },
    "军工": {
        "primary_sectors": ["国防军工", "航空装备"],
        "related_sectors": [
            "航空装备Ⅱ",
            "航空装备Ⅲ",
            "航天装备",
            "航天装备Ⅱ",
            "航天装备Ⅲ",
            "商业航天",
            "低空经济",
        ],
    },
    "证券金融": {
        "primary_sectors": ["证券", "保险", "银行"],
        "related_sectors": ["证券Ⅱ", "证券Ⅲ", "保险Ⅱ", "保险Ⅲ", "多元金融", "互联网金融", "资本市场"],
    },
}

THEME_DEFINITIONS = FALLBACK_THEME_DEFINITIONS

THEME_MODE_LABELS = {
    "strict_representative": "严格代表口径",
    "representative": "代表口径",
    "breadth": "观察强度",
}

THEME_STATUS_THRESHOLDS = [
    {"status": "强流入", "status_level": "positive_strong", "lower_bound": 30.0, "upper_bound": None, "lower_inclusive": True, "upper_inclusive": False},
    {"status": "弱流入", "status_level": "positive_weak", "lower_bound": 5.0, "upper_bound": 30.0, "lower_inclusive": True, "upper_inclusive": False},
    {"status": "分歧/中性", "status_level": "neutral", "lower_bound": -5.0, "upper_bound": 5.0, "lower_inclusive": False, "upper_inclusive": False},
    {"status": "弱流出", "status_level": "negative_weak", "lower_bound": -30.0, "upper_bound": -5.0, "lower_inclusive": False, "upper_inclusive": True},
    {"status": "强流出", "status_level": "negative_strong", "lower_bound": None, "upper_bound": -30.0, "lower_inclusive": False, "upper_inclusive": True},
]


def normalize_sector_name(name: str) -> str:
    return "" if name is None else str(name).strip().replace(" ", "").upper()


def is_exact_match(sector_name: str, candidates: list[str]) -> bool:
    text = normalize_sector_name(sector_name)
    return any(text == normalize_sector_name(candidate) for candidate in candidates)


def is_contains_match(sector_name: str, candidates: list[str]) -> bool:
    text = normalize_sector_name(sector_name)
    return any(normalize_sector_name(candidate) in text for candidate in candidates if normalize_sector_name(candidate))


def _filter_exact(df: pd.DataFrame, candidates: list[str]) -> pd.DataFrame:
    return df[df["sector_name"].map(lambda value: is_exact_match(value, candidates))]


def _filter_contains(df: pd.DataFrame, candidates: list[str], exact_df: pd.DataFrame) -> pd.DataFrame:
    contains = df[df["sector_name"].map(lambda value: is_contains_match(value, candidates))]
    return contains.drop(index=exact_df.index, errors="ignore")


def _dedupe_concat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    available = [frame for frame in frames if frame is not None and not frame.empty]
    if not available:
        return pd.DataFrame()
    return pd.concat(available, ignore_index=False).loc[lambda frame: ~frame.index.duplicated(keep="first")]


def split_theme_matches(df: pd.DataFrame, theme_def: dict) -> dict[str, pd.DataFrame]:
    primary = theme_def["primary_sectors"]
    related = theme_def["related_sectors"]
    primary_exact = _filter_exact(df, primary)
    related_exact = _filter_exact(df.drop(index=primary_exact.index, errors="ignore"), related)
    matched_exact = _dedupe_concat([primary_exact, related_exact])
    remaining = df.drop(index=matched_exact.index, errors="ignore")
    primary_contains = _filter_contains(remaining, primary, primary_exact)
    remaining = remaining.drop(index=primary_contains.index, errors="ignore")
    related_contains = _filter_contains(remaining, related, related_exact)
    all_matched = _dedupe_concat([primary_exact, related_exact, primary_contains, related_contains])
    return {
        "primary_exact_df": primary_exact,
        "primary_contains_df": primary_contains,
        "related_exact_df": related_exact,
        "related_contains_df": related_contains,
        "all_matched_df": all_matched,
    }


def get_theme_definitions() -> dict[str, dict[str, list[str]]]:
    try:
        definitions = taxonomy_to_theme_definitions(load_theme_taxonomy())
    except Exception:
        return FALLBACK_THEME_DEFINITIONS
    return definitions or FALLBACK_THEME_DEFINITIONS


def map_to_theme(sector_name: str) -> str | None:
    if not sector_name:
        return None
    row = pd.DataFrame([{"sector_name": sector_name}])
    for theme_name, theme_def in get_theme_definitions().items():
        if not split_theme_matches(row, theme_def)["all_matched_df"].empty:
            return theme_name
    return None


def classify_theme_status(row) -> tuple[str, str]:
    value = float(row.get("main_net_inflow_billion", 0) or 0)
    if value >= 30:
        return "强流入", "positive_strong"
    if 5 <= value < 30:
        return "弱流入", "positive_weak"
    if -5 < value < 5:
        return "分歧/中性", "neutral"
    if -30 < value <= -5:
        return "弱流出", "negative_weak"
    return "强流出", "negative_strong"


def get_theme_status_thresholds() -> list[dict]:
    return [dict(item) for item in THEME_STATUS_THRESHOLDS]


def _normalize_theme_mode(theme_mode: str) -> ThemeMode:
    if theme_mode == "breadth":
        return "breadth"
    if theme_mode == "representative":
        return "representative"
    return "strict_representative"


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
    if group is None or group.empty:
        return []
    return group["sector_name"].dropna().astype(str).drop_duplicates().tolist()


def _safe_trace_value(row: pd.Series, column: str):
    value = row.get(column)
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _member_trace_rows(
    theme_def: dict,
    matches: dict[str, pd.DataFrame],
    used_group: pd.DataFrame,
) -> list[dict]:
    used_indices = set(used_group.index.tolist()) if used_group is not None and not used_group.empty else set()
    role_frames = [
        ("core", "exact", matches.get("primary_exact_df")),
        ("related", "exact", matches.get("related_exact_df")),
        ("core", "contains", matches.get("primary_contains_df")),
        ("related", "contains", matches.get("related_contains_df")),
    ]
    rows: list[dict] = []
    seen: set[object] = set()
    for role, match_type, frame in role_frames:
        if frame is None or frame.empty:
            continue
        for idx, row in frame.iterrows():
            if idx in seen:
                continue
            seen.add(idx)
            included = idx in used_indices
            value = pd.to_numeric(pd.Series([row.get("main_net_inflow_billion")]), errors="coerce").iloc[0]
            rows.append(
                {
                    "member_name": str(row.get("sector_name") or ""),
                    "member_role": role,
                    "match_type": match_type,
                    "matched_source_row": str(row.get("sector_name") or ""),
                    "input_value": None if pd.isna(value) else float(value),
                    "normalized_value": None if pd.isna(value) else float(value),
                    "included": bool(included),
                    "exclusion_reason": "" if included else "当前口径未纳入该匹配成员",
                    "sector_type": _safe_trace_value(row, "sector_type"),
                    "captured_time": _safe_trace_value(row, "captured_time"),
                    "trade_date": _safe_trace_value(row, "trade_date"),
                }
            )
    configured = set(theme_def.get("primary_sectors", [])) | set(theme_def.get("related_sectors", []))
    matched_names = {item["member_name"] for item in rows}
    for member in sorted(configured - matched_names):
        role = "core" if member in set(theme_def.get("primary_sectors", [])) else "related"
        rows.append(
            {
                "member_name": member,
                "member_role": role,
                "match_type": "unmatched",
                "matched_source_row": None,
                "input_value": None,
                "normalized_value": None,
                "included": False,
                "exclusion_reason": "当前快照未匹配到该配置成员",
                "sector_type": None,
                "captured_time": None,
                "trade_date": None,
            }
        )
    return rows


def _build_trace_record(
    theme_name: str,
    theme_def: dict,
    source_group: pd.DataFrame,
    used_group: pd.DataFrame,
    matches: dict[str, pd.DataFrame],
    theme_mode: ThemeMode,
    match_strategy: str,
    theme_value_label: str,
    row: dict,
) -> dict:
    members = _member_trace_rows(theme_def, matches, used_group)
    included_values = [item["input_value"] for item in members if item.get("included") and item.get("input_value") is not None]
    configured_count = len(set(theme_def.get("primary_sectors", [])) | set(theme_def.get("related_sectors", [])))
    return {
        "theme_name": theme_name,
        "theme_mode": theme_mode,
        "theme_value_label": theme_value_label,
        "match_strategy": match_strategy,
        "aggregation_method": "sum(main_net_inflow_billion) over selected matched members",
        "aggregation_inputs": included_values,
        "aggregate_value": float(row.get("main_net_inflow_billion") or 0),
        "derived_state": row.get("theme_status"),
        "derived_state_level": row.get("theme_status_level"),
        "thresholds": get_theme_status_thresholds(),
        "configured_member_count": configured_count,
        "matched_member_count": int(len(source_group)) if source_group is not None else 0,
        "used_member_count": int(len(used_group)) if used_group is not None else 0,
        "unmatched_member_count": int(sum(1 for item in members if item.get("match_type") == "unmatched")),
        "matched_members": [item for item in members if item.get("matched_source_row")],
        "all_members": members,
        "used_sectors": row.get("used_sectors"),
        "source_sectors": row.get("source_sectors"),
        "canonical_row": dict(row),
    }


def _join_sectors(group: pd.DataFrame) -> str:
    return "，".join(_sectors_for_group(group))


def _select_used_group(matches: dict[str, pd.DataFrame], theme_mode: ThemeMode) -> tuple[pd.DataFrame, str, str]:
    if theme_mode == "breadth":
        return matches["all_matched_df"], "breadth_all", "观察强度"
    if theme_mode == "strict_representative":
        if not matches["primary_exact_df"].empty:
            return matches["primary_exact_df"], "primary_exact", "严格代表口径"
        if not matches["related_exact_df"].empty:
            return matches["related_exact_df"], "related_exact_fallback", "严格代表口径-相关替代"
        return pd.DataFrame(), "no_strict_match", "严格代表口径"
    if not matches["primary_exact_df"].empty:
        return matches["primary_exact_df"], "primary_exact", "代表口径"
    if not matches["primary_contains_df"].empty:
        return matches["primary_contains_df"], "primary_contains", "代表口径"
    if not matches["related_exact_df"].empty:
        return matches["related_exact_df"], "related_exact_fallback", "代表口径"
    if not matches["related_contains_df"].empty:
        return matches["related_contains_df"], "related_contains_fallback", "代表口径"
    return pd.DataFrame(), "no_match", "代表口径"


def _build_theme_row(
    theme_name: str,
    source_group: pd.DataFrame,
    used_group: pd.DataFrame,
    theme_mode: ThemeMode,
    match_strategy: str,
    theme_value_label: str,
) -> dict:
    first = source_group.iloc[0]
    inflow = used_group["main_net_inflow_billion"].sum()
    row = {
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
        "source_sectors": _join_sectors(source_group),
        "used_sectors": _join_sectors(used_group),
        "source_sector_count": len(_sectors_for_group(source_group)),
        "used_sector_count": len(_sectors_for_group(used_group)),
        "aggregation_mode": theme_mode,
        "theme_value_label": theme_value_label,
        "match_strategy": match_strategy,
    }
    row["theme_status"], row["theme_status_level"] = classify_theme_status(row)
    return row


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["main_net_inflow_billion"] = pd.to_numeric(work["main_net_inflow_billion"], errors="coerce")
    return work.dropna(subset=["sector_name", "main_net_inflow_billion"])


def _build_rows_for_frame(df: pd.DataFrame, theme_mode: ThemeMode) -> list[dict]:
    rows = []
    remaining = df.copy()
    for theme_name, theme_def in get_theme_definitions().items():
        matches = split_theme_matches(remaining, theme_def)
        source_group = matches["all_matched_df"]
        if source_group.empty:
            continue
        used_group, match_strategy, label = _select_used_group(matches, theme_mode)
        if used_group.empty:
            remaining = remaining.drop(index=source_group.index, errors="ignore")
            continue
        rows.append(_build_theme_row(theme_name, source_group, used_group, theme_mode, match_strategy, label))
        remaining = remaining.drop(index=source_group.index, errors="ignore")
    return rows


def _build_rows_and_traces_for_frame(df: pd.DataFrame, theme_mode: ThemeMode) -> tuple[list[dict], list[dict]]:
    rows = []
    traces = []
    remaining = df.copy()
    for theme_name, theme_def in get_theme_definitions().items():
        matches = split_theme_matches(remaining, theme_def)
        source_group = matches["all_matched_df"]
        if source_group.empty:
            continue
        used_group, match_strategy, label = _select_used_group(matches, theme_mode)
        if used_group.empty:
            remaining = remaining.drop(index=source_group.index, errors="ignore")
            continue
        row = _build_theme_row(theme_name, source_group, used_group, theme_mode, match_strategy, label)
        rows.append(row)
        traces.append(_build_trace_record(theme_name, theme_def, source_group, used_group, matches, theme_mode, match_strategy, label, row))
        remaining = remaining.drop(index=source_group.index, errors="ignore")
    return rows, traces


def build_theme_snapshot(
    latest_df: pd.DataFrame,
    theme_mode: str = "strict_representative",
) -> pd.DataFrame:
    if latest_df is None or latest_df.empty:
        return pd.DataFrame()
    mode = _normalize_theme_mode(theme_mode)
    rows = _build_rows_for_frame(_prepare_df(latest_df), mode)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("main_net_inflow_billion", ascending=False).reset_index(drop=True)


def build_theme_snapshot_with_trace(
    latest_df: pd.DataFrame,
    theme_mode: str = "strict_representative",
) -> tuple[pd.DataFrame, dict[str, dict]]:
    if latest_df is None or latest_df.empty:
        return pd.DataFrame(), {}
    mode = _normalize_theme_mode(theme_mode)
    rows, traces = _build_rows_and_traces_for_frame(_prepare_df(latest_df), mode)
    if not rows:
        return pd.DataFrame(), {}
    out = pd.DataFrame(rows).sort_values("main_net_inflow_billion", ascending=False).reset_index(drop=True)
    trace_map = {str(trace.get("theme_name")): trace for trace in traces}
    return out, trace_map


def apply_theme_pool_to_ticks(
    ticks_df: pd.DataFrame,
    theme_mode: str = "strict_representative",
) -> pd.DataFrame:
    if ticks_df is None or ticks_df.empty:
        return pd.DataFrame()
    mode = _normalize_theme_mode(theme_mode)
    df = _prepare_df(ticks_df)
    if df.empty:
        return pd.DataFrame()

    group_keys = ["trade_date", "captured_at", "captured_time", "sector_type"]
    rows = []
    for _, frame in df.groupby(group_keys, dropna=False, sort=False):
        rows.extend(_build_rows_for_frame(frame, mode))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["captured_at", "main_net_inflow_billion"]).reset_index(drop=True)
