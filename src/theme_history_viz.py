from __future__ import annotations

import pandas as pd


CHART_OPTIONS = [
    "主题净流入折线图",
    "主题历史热力矩阵",
    "最新主题表现柱状图",
    "主题状态时间线",
]
DEFAULT_CHART_OPTION = CHART_OPTIONS[0]
FORBIDDEN_THEME_HISTORY_VIZ_WORDS = (
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
)


def get_theme_history_chart_options() -> list[str]:
    return list(CHART_OPTIONS)


def normalize_theme_history_chart_option(option: str | None) -> str:
    if option in CHART_OPTIONS:
        return str(option)
    return DEFAULT_CHART_OPTION


def _empty_line_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "source_type",
            "data_date",
            "captured_time",
            "theme_name",
            "theme_group",
            "main_net_inflow_billion",
            "theme_status",
        ]
    )


def _latest_theme_names(theme_history_df: pd.DataFrame, top_n: int) -> list[str]:
    if theme_history_df is None or theme_history_df.empty:
        return []
    df = theme_history_df.copy()
    if "data_date" not in df.columns or "theme_name" not in df.columns:
        return []
    df["main_net_inflow_billion"] = pd.to_numeric(df.get("main_net_inflow_billion"), errors="coerce")
    latest_date = df["data_date"].dropna().astype(str).max()
    latest = df[df["data_date"].astype(str).eq(str(latest_date))].copy()
    if latest.empty:
        return []
    latest["_abs_value"] = latest["main_net_inflow_billion"].abs()
    return latest.sort_values("_abs_value", ascending=False)["theme_name"].dropna().astype(str).drop_duplicates().head(top_n).tolist()


def prepare_theme_history_line_data(
    theme_history_df: pd.DataFrame,
    selected_themes: list[str] | None = None,
    top_n: int = 5,
) -> pd.DataFrame:
    if theme_history_df is None or theme_history_df.empty:
        return _empty_line_df()
    required = {"source_type", "data_date", "captured_time", "theme_name", "main_net_inflow_billion"}
    if not required.issubset(theme_history_df.columns):
        return _empty_line_df()
    limit = max(1, min(int(top_n or 5), 10))
    themes = [str(item) for item in (selected_themes or []) if str(item).strip()]
    if not themes:
        themes = _latest_theme_names(theme_history_df, limit)
    if not themes:
        return _empty_line_df()
    df = theme_history_df[theme_history_df["theme_name"].astype(str).isin(themes)].copy()
    if df.empty:
        return _empty_line_df()
    for col in ["theme_group", "theme_status"]:
        if col not in df.columns:
            df[col] = ""
    df["main_net_inflow_billion"] = pd.to_numeric(df["main_net_inflow_billion"], errors="coerce")
    return df[
        [
            "source_type",
            "data_date",
            "captured_time",
            "theme_name",
            "theme_group",
            "main_net_inflow_billion",
            "theme_status",
        ]
    ].sort_values(["source_type", "theme_name", "data_date", "captured_time"]).reset_index(drop=True)


def prepare_theme_history_heatmap_data(
    theme_history_df: pd.DataFrame,
    top_n: int = 8,
    value_column: str = "main_net_inflow_billion",
) -> pd.DataFrame:
    if theme_history_df is None or theme_history_df.empty or value_column not in theme_history_df.columns:
        return pd.DataFrame()
    if "data_date" not in theme_history_df.columns or "theme_name" not in theme_history_df.columns:
        return pd.DataFrame()
    limit = max(1, min(int(top_n or 8), 12))
    themes = _latest_theme_names(theme_history_df, limit)
    if not themes:
        return pd.DataFrame()
    df = theme_history_df[theme_history_df["theme_name"].astype(str).isin(themes)].copy()
    if df.empty:
        return pd.DataFrame()
    df[value_column] = pd.to_numeric(df[value_column], errors="coerce")
    matrix = df.pivot_table(index="data_date", columns="theme_name", values=value_column, aggfunc="last")
    matrix = matrix.reindex(columns=themes)
    return matrix.sort_index().reset_index()


def prepare_latest_theme_bar_data(
    theme_history_df: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    if theme_history_df is None or theme_history_df.empty:
        return pd.DataFrame(
            columns=[
                "source_type",
                "data_date",
                "captured_time",
                "theme_name",
                "theme_group",
                "main_net_inflow_billion",
                "theme_status",
                "source_count",
            ]
        )
    required = {"source_type", "data_date", "captured_time", "theme_name", "main_net_inflow_billion"}
    if not required.issubset(theme_history_df.columns):
        return pd.DataFrame()
    limit = max(1, min(int(top_n or 10), 20))
    df = theme_history_df.copy()
    latest_date = df["data_date"].dropna().astype(str).max()
    latest = df[df["data_date"].astype(str).eq(str(latest_date))].copy()
    if latest.empty:
        return pd.DataFrame()
    latest_time = latest.groupby("source_type")["captured_time"].transform("max")
    latest = latest[latest["captured_time"].eq(latest_time)].copy()
    for col in ["theme_group", "theme_status", "source_count"]:
        if col not in latest.columns:
            latest[col] = "" if col != "source_count" else 0
    latest["main_net_inflow_billion"] = pd.to_numeric(latest["main_net_inflow_billion"], errors="coerce")
    latest["_abs_value"] = latest["main_net_inflow_billion"].abs()
    return latest.sort_values("_abs_value", ascending=False)[
        [
            "source_type",
            "data_date",
            "captured_time",
            "theme_name",
            "theme_group",
            "main_net_inflow_billion",
            "theme_status",
            "source_count",
        ]
    ].head(limit).reset_index(drop=True)


def prepare_status_timeline_compact(
    timeline_df: pd.DataFrame,
    selected_themes: list[str] | None = None,
    max_rows: int = 80,
) -> pd.DataFrame:
    columns = [
        "source_type",
        "theme_name",
        "data_date",
        "theme_status",
        "status_change_label",
        "main_net_inflow_billion",
        "status_change_reason",
    ]
    if timeline_df is None or timeline_df.empty:
        return pd.DataFrame(columns=columns)
    df = timeline_df.copy()
    if "theme_name" not in df.columns:
        return pd.DataFrame(columns=columns)
    themes = [str(item) for item in (selected_themes or []) if str(item).strip()]
    if themes:
        df = df[df["theme_name"].astype(str).isin(themes)].copy()
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df["main_net_inflow_billion"] = pd.to_numeric(df["main_net_inflow_billion"], errors="coerce")
    limit = max(1, min(int(max_rows or 80), 200))
    return df[columns].sort_values(["source_type", "theme_name", "data_date"]).head(limit).reset_index(drop=True)


def build_theme_history_visual_summary(
    theme_history_df: pd.DataFrame,
    timeline_df: pd.DataFrame | None = None,
    top_n: int = 5,
) -> dict:
    if theme_history_df is None or theme_history_df.empty:
        return {
            "visual_available": False,
            "source_type_count": 0,
            "date_count": 0,
            "theme_count": 0,
            "latest_date": None,
            "line_theme_count": 0,
            "heatmap_theme_count": 0,
            "latest_bar_count": 0,
            "highlighted_themes": [],
            "visual_summary_label": "暂无可视化数据",
            "visual_summary_reason": "当前 warehouse 中暂无可用于主题历史图表的数据。",
            "warnings": [],
            "errors": [],
        }
    df = theme_history_df.copy()
    source_types = sorted(df.get("source_type", pd.Series(dtype=str)).dropna().astype(str).str.upper().unique().tolist())
    latest_date = df["data_date"].dropna().astype(str).max() if "data_date" in df.columns else None
    limit = max(1, min(int(top_n or 5), 10))
    highlighted = _latest_theme_names(df, limit)
    line_df = prepare_theme_history_line_data(df, highlighted, top_n=limit)
    heatmap_df = prepare_theme_history_heatmap_data(df, top_n=limit)
    latest_bar_df = prepare_latest_theme_bar_data(df, top_n=limit)
    date_count = int(df["data_date"].nunique()) if "data_date" in df.columns else 0
    sample_only = bool(source_types) and set(source_types) == {"SAMPLE"}
    if sample_only:
        label = "仅 SAMPLE 图表可用"
        reason = "当前图表基于 SAMPLE 合成演示数据生成，仅用于展示主题历史观察流程，不代表真实行情。"
    elif date_count < 2:
        label = "主题历史样本较少"
        reason = "当前主题历史样本日期较少，图表仅适合作为已保存状态的轻量观察。"
    else:
        label = "主题历史图表可用"
        reason = "当前 warehouse 中已有主题历史数据，可用于只读展示已保存的主题资金状态。"
    return {
        "visual_available": True,
        "source_type_count": len(source_types),
        "date_count": date_count,
        "theme_count": int(df["theme_name"].nunique()) if "theme_name" in df.columns else 0,
        "latest_date": latest_date,
        "line_theme_count": int(line_df["theme_name"].nunique()) if not line_df.empty else 0,
        "heatmap_theme_count": max(0, len(heatmap_df.columns) - 1) if not heatmap_df.empty else 0,
        "latest_bar_count": len(latest_bar_df),
        "highlighted_themes": highlighted,
        "visual_summary_label": label,
        "visual_summary_reason": reason,
        "warnings": [],
        "errors": [],
    }


def build_theme_history_visual_notes(
    source_type: str | None,
    theme_mode: str,
    latest_per_day: bool,
    is_sample_only: bool = False,
) -> list[str]:
    source = str(source_type or "ALL").upper()
    notes = [
        f"当前图表基于 warehouse 中已导入的历史快照生成，source_type={source}。",
        "CSV 仍是主数据来源；warehouse 只是可重建索引。",
        f"当前主题口径：{theme_mode}。",
    ]
    if latest_per_day:
        notes.append("已启用每日期最新快照：每个日期只取最新 captured_time。")
    else:
        notes.append("当前包含多个 captured_time，适合观察日内样本与日期样本的混合状态。")
    if is_sample_only:
        notes.append("当前为 SAMPLE 合成演示数据，仅用于公开演示，不代表真实行情。")
    if source == "ALL":
        notes.append("ALL 可能包含多个 source_type，解释时需区分 LOCAL 与 SAMPLE 来源。")
    notes.append("图表只描述已保存的历史资金状态，不预测未来走势，不构成投资建议。")
    return notes


def validate_theme_history_viz_text(text: str) -> list[str]:
    value = str(text or "")
    return [word for word in FORBIDDEN_THEME_HISTORY_VIZ_WORDS if word in value]
