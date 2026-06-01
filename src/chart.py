from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go

from src.config import DEFAULT_TOP_IN, DEFAULT_TOP_OUT, TIMEZONE
from src.utils import format_billion


POSITIVE_COLORS = [
    "#ffcc33",
    "#ff6b4a",
    "#f94144",
    "#f8961e",
    "#f9c74f",
    "#ff8fab",
    "#ffb703",
    "#fb5607",
    "#ffd166",
    "#ef476f",
]
NEGATIVE_COLORS = [
    "#00d084",
    "#2ec4b6",
    "#06d6a0",
    "#4cc9f0",
    "#48cae4",
    "#80ed99",
    "#90e0ef",
    "#5eead4",
    "#64dfdf",
    "#38bdf8",
]
NEUTRAL_COLORS = ["#c9d1d9", "#9ca3af", "#d1d5db"]


def _empty_figure(message: str = "暂无数据") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#050505",
        plot_bgcolor="#050505",
        height=760,
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 24, "color": "#c9d1d9"},
            }
        ],
    )
    return fig


def _selected_sector_names(
    latest_df: pd.DataFrame,
    top_in: int,
    top_out: int,
) -> list[str]:
    latest = latest_df.copy()
    latest["main_net_inflow_billion"] = pd.to_numeric(latest["main_net_inflow_billion"], errors="coerce")
    inflow = latest[latest["main_net_inflow_billion"].gt(0)].sort_values(
        "main_net_inflow_billion", ascending=False
    ).head(top_in)
    outflow = latest[latest["main_net_inflow_billion"].lt(0)].sort_values(
        "main_net_inflow_billion", ascending=True
    ).head(top_out)
    selected = pd.concat([inflow, outflow], ignore_index=True)
    return selected["sector_name"].drop_duplicates().tolist()


def _avoid_label_collision(values: list[float], min_gap: float) -> list[float]:
    if not values:
        return []
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    adjusted = [0.0] * len(values)
    last_y = -math.inf
    for idx, value in indexed:
        y = value
        if y - last_y < min_gap:
            y = last_y + min_gap
        adjusted[idx] = y
        last_y = y
    return adjusted


def build_flow_chart(
    ticks_df: pd.DataFrame,
    top_in: int = DEFAULT_TOP_IN,
    top_out: int = DEFAULT_TOP_OUT,
) -> go.Figure:
    if ticks_df is None or ticks_df.empty:
        return _empty_figure()

    df = ticks_df.copy()
    df["captured_at"] = pd.to_datetime(df["captured_at"], errors="coerce")
    if getattr(df["captured_at"].dt, "tz", None) is not None:
        df["captured_at"] = df["captured_at"].dt.tz_convert(TIMEZONE).dt.tz_localize(None)
    df = df.dropna(subset=["captured_at", "sector_name", "main_net_inflow_billion"])
    if df.empty:
        return _empty_figure()

    latest_at = df["captured_at"].max()
    latest_df = df[df["captured_at"].eq(latest_at)]
    selected_names = _selected_sector_names(latest_df, top_in, top_out)
    plot_df = df[df["sector_name"].isin(selected_names)].sort_values("captured_at")
    if plot_df.empty:
        return _empty_figure()

    y_values = plot_df["main_net_inflow_billion"]
    y_min = min(float(y_values.min()), 0.0)
    y_max = max(float(y_values.max()), 0.0)
    y_span = max(y_max - y_min, 1.0)
    label_gap = y_span * 0.035

    fig = go.Figure()
    label_items = []
    positive_index = 0
    negative_index = 0
    neutral_index = 0
    few_snapshots = df["captured_time"].nunique() < 3 if "captured_time" in df.columns else df["captured_at"].nunique() < 3

    latest_selected = latest_df[latest_df["sector_name"].isin(selected_names)].copy()
    latest_selected = latest_selected.sort_values("main_net_inflow_billion", ascending=False)

    for _, row in latest_selected.iterrows():
        name = row["sector_name"]
        series = plot_df[plot_df["sector_name"].eq(name)].sort_values("captured_at")
        latest_value = float(series["main_net_inflow_billion"].iloc[-1])
        source_sectors = ""
        used_sectors = ""
        aggregation_mode = ""
        theme_value_label = ""
        match_strategy = ""
        theme_status = ""
        if "source_sectors" in series.columns:
            source_value = series["source_sectors"].dropna()
            if not source_value.empty:
                source_sectors = str(source_value.iloc[-1])
        if "used_sectors" in series.columns:
            used_value = series["used_sectors"].dropna()
            if not used_value.empty:
                used_sectors = str(used_value.iloc[-1])
        if "aggregation_mode" in series.columns:
            mode_value = series["aggregation_mode"].dropna()
            if not mode_value.empty:
                aggregation_mode = str(mode_value.iloc[-1])
        if "theme_value_label" in series.columns:
            label_value = series["theme_value_label"].dropna()
            if not label_value.empty:
                theme_value_label = str(label_value.iloc[-1])
        if "match_strategy" in series.columns:
            strategy_value = series["match_strategy"].dropna()
            if not strategy_value.empty:
                match_strategy = str(strategy_value.iloc[-1])
        if "theme_status" in series.columns:
            status_value = series["theme_status"].dropna()
            if not status_value.empty:
                theme_status = str(status_value.iloc[-1])
        if latest_value > 0:
            color = POSITIVE_COLORS[positive_index % len(POSITIVE_COLORS)]
            positive_index += 1
        elif latest_value < 0:
            color = NEGATIVE_COLORS[negative_index % len(NEGATIVE_COLORS)]
            negative_index += 1
        else:
            color = NEUTRAL_COLORS[neutral_index % len(NEUTRAL_COLORS)]
            neutral_index += 1

        fig.add_trace(
            go.Scatter(
                x=series["captured_at"],
                y=series["main_net_inflow_billion"],
                mode="lines",
                name=name,
                line={"width": 2, "color": color},
                hovertemplate=(
                    "时间：%{x|%H:%M:%S}<br>"
                    f"板块：{name}<br>"
                    "主力净流入：%{y:.1f} 亿"
                    + (f"<br>资金流状态：{theme_status}" if theme_status else "")
                    + (f"<br>主题口径：{aggregation_mode}" if aggregation_mode else "")
                    + (f"<br>数值标签：{theme_value_label}" if theme_value_label else "")
                    + (f"<br>匹配策略：{match_strategy}" if match_strategy else "")
                    + (f"<br>使用板块：{used_sectors}" if used_sectors else "")
                    + (f"<br>来源板块：{source_sectors}" if source_sectors else "")
                    + "<extra></extra>"
                ),
                showlegend=False,
            )
        )
        label_items.append(
            {
                "name": name,
                "value": latest_value,
                "x": series["captured_at"].iloc[-1],
                "color": color,
                "aggregation_mode": aggregation_mode,
                "theme_value_label": theme_value_label,
            }
        )

    adjusted_y = _avoid_label_collision([item["value"] for item in label_items], label_gap)
    for item, label_y in zip(label_items, adjusted_y):
        if item.get("aggregation_mode") == "breadth" and item.get("theme_value_label"):
            label_text = f"{item['name']} {item['theme_value_label']} {format_billion(item['value'])}"
        else:
            label_text = f"{item['name']} {format_billion(item['value'])}"
        fig.add_annotation(
            x=1.01,
            y=label_y,
            xref="paper",
            yref="y",
            text=label_text,
            xanchor="left",
            align="left",
            xshift=0,
            showarrow=False,
            font={"size": 13, "color": item["color"]},
            bgcolor="rgba(5,5,5,0.72)",
            bordercolor="rgba(220,220,220,0.24)",
            borderwidth=1,
            borderpad=4,
        )

    if not plot_df.empty:
        trade_day = plot_df["captured_at"].dt.strftime("%Y-%m-%d").iloc[-1]
        tick_texts = [
            "09:30",
            "10:00",
            "10:30",
            "11:30",
            "13:00",
            "13:30",
            "14:00",
            "14:30",
            "15:00",
        ]
        tick_vals = pd.to_datetime([f"{trade_day} {time}" for time in tick_texts])
    else:
        tick_texts = []
        tick_vals = []

    x_min = pd.to_datetime(f"{plot_df['captured_at'].dt.strftime('%Y-%m-%d').iloc[-1]} 09:30")
    x_max = pd.to_datetime(f"{plot_df['captured_at'].dt.strftime('%Y-%m-%d').iloc[-1]} 15:25")

    fig.add_hline(y=0, line_dash="dash", line_width=1.2, line_color="rgba(245,245,245,0.68)")
    if few_snapshots:
        fig.add_annotation(
            x=0.5,
            y=1.04,
            xref="paper",
            yref="paper",
            text="当前快照数量较少，曲线仍在形成中。",
            showarrow=False,
            font={"size": 13, "color": "#ffd166"},
            bgcolor="rgba(20,20,20,0.82)",
            bordercolor="rgba(255,209,102,0.35)",
            borderwidth=1,
            borderpad=5,
        )
    fig.update_layout(
        template="plotly_dark",
        height=720,
        paper_bgcolor="#050505",
        plot_bgcolor="#050505",
        margin={"l": 64, "r": 220, "t": 38, "b": 52},
        hovermode="x unified",
        font={"family": "Arial, Helvetica, sans-serif", "color": "#d1d5db"},
        xaxis={
            "range": [x_min, x_max],
            "tickmode": "array",
            "tickvals": tick_vals,
            "ticktext": tick_texts,
            "showgrid": False,
            "zeroline": False,
            "color": "#a6adbb",
            "tickangle": 0,
        },
        yaxis={
            "title": {"text": "亿元", "font": {"color": "#c9d1d9"}},
            "gridcolor": "rgba(255,255,255,0.07)",
            "zeroline": False,
            "color": "#a6adbb",
            "ticksuffix": " 亿",
        },
    )
    return fig
