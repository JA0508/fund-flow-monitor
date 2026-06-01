from __future__ import annotations

import math

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src.chart import build_flow_chart
from src.config import (
    DEFAULT_SECTOR_TYPE,
    DEFAULT_TOP_IN,
    DEFAULT_TOP_OUT,
    FETCH_ALLOWED_STATUSES,
    REFRESH_INTERVAL_SECONDS,
    SECTOR_TYPES,
    TIMEZONE,
)
from src.data_source import fetch_sector_flow
from src.market_time import get_market_status
from src.storage import append_snapshot, load_latest_ticks, load_today_ticks
from src.theme_pool import apply_theme_pool_to_ticks
from src.transform import normalize_sector_flow
from src.ui_components import (
    inject_global_css,
    render_error_box,
    render_header,
    render_rank_tables,
    render_status_bar,
)
from src.utils import get_china_now


st.set_page_config(
    page_title="A股板块主力资金净流入实时监测",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _make_demo_data(sector_type: str, now) -> pd.DataFrame:
    names = [
        "电力",
        "PCB",
        "银行",
        "煤炭",
        "证券",
        "有色金属",
        "半导体",
        "机器人",
        "新能源车",
        "AI应用",
        "白酒",
        "医药商业",
        "游戏",
        "光伏设备",
        "军工",
        "算力租赁",
        "房地产",
        "消费电子",
        "低空经济",
        "稀土永磁",
        "CPO",
        "芯片",
        "传媒",
        "钢铁",
        "港口航运",
    ]
    start = (
        pd.Timestamp(now)
        .tz_convert(TIMEZONE)
        .tz_localize(None)
        .normalize()
        + pd.Timedelta(hours=9, minutes=30)
    )
    points = []
    current = pd.Timestamp(now).tz_convert(TIMEZONE).tz_localize(None)
    periods = max(2, min(48, int((current - start).total_seconds() // 300) + 1))
    for step in range(periods):
        captured_at = start + pd.Timedelta(minutes=step * 5)
        for idx, name in enumerate(names):
            direction = 1 if idx < 10 else -1
            amplitude = (idx % 8 + 2) * 1.8
            drift = direction * (step + 1) * (0.32 + idx * 0.015)
            wave = math.sin(step / 2.7 + idx) * amplitude
            billion = drift + wave
            points.append(
                {
                    "trade_date": captured_at.strftime("%Y-%m-%d"),
                    "captured_at": captured_at,
                    "captured_time": captured_at.strftime("%H:%M:%S"),
                    "sector_type": sector_type,
                    "sector_code": f"DEMO{idx:03d}",
                    "sector_name": name,
                    "change_pct": round(math.sin(idx + step / 3) * 2.8, 2),
                    "main_net_inflow_yuan": billion * 100_000_000,
                    "main_net_inflow_billion": billion,
                    "main_net_ratio": round(math.cos(idx / 2 + step / 5) * 6, 2),
                    "super_large_net_inflow_yuan": billion * 60_000_000,
                    "large_net_inflow_yuan": billion * 30_000_000,
                    "medium_net_inflow_yuan": -billion * 15_000_000,
                    "small_net_inflow_yuan": -billion * 10_000_000,
                    "leading_stock": f"示例股{idx + 1}",
                    "source": "DEMO",
                }
            )
    return pd.DataFrame(points)


def _latest_snapshot(ticks_df: pd.DataFrame) -> pd.DataFrame:
    if ticks_df.empty or "captured_at" not in ticks_df.columns:
        return pd.DataFrame()
    df = ticks_df.copy()
    df["captured_at"] = pd.to_datetime(df["captured_at"], errors="coerce")
    if getattr(df["captured_at"].dt, "tz", None) is not None:
        df["captured_at"] = df["captured_at"].dt.tz_convert(TIMEZONE).dt.tz_localize(None)
    df = df.dropna(subset=["captured_at"])
    if df.empty:
        return pd.DataFrame()
    return df[df["captured_at"].eq(df["captured_at"].max())]


def _latest_time(ticks_df: pd.DataFrame, fallback: str) -> str:
    latest = _latest_snapshot(ticks_df)
    if latest.empty:
        return fallback
    value = latest["captured_time"].iloc[0] if "captured_time" in latest.columns else None
    if pd.isna(value) or not value:
        return pd.Timestamp(latest["captured_at"].iloc[0]).strftime("%H:%M:%S")
    return str(value)


def _filter_sector_type(ticks_df: pd.DataFrame, sector_type: str) -> pd.DataFrame:
    if ticks_df.empty or "sector_type" not in ticks_df.columns:
        return ticks_df
    return ticks_df[ticks_df["sector_type"].eq(sector_type)].copy()


def _load_cache_ticks(trade_date: str, sector_type: str) -> pd.DataFrame:
    ticks = _filter_sector_type(load_today_ticks(trade_date), sector_type)
    if ticks.empty:
        ticks = _filter_sector_type(load_latest_ticks(), sector_type)
    return ticks


def main() -> None:
    inject_global_css()

    with st.sidebar:
        st.header("监测设置")
        display_mode = st.selectbox("展示模式", ("基金观察池", "原始板块"), index=0)
        theme_mode_label = None
        theme_mode = "representative"
        if display_mode == "基金观察池":
            theme_mode_label = st.selectbox("主题口径", ("代表口径", "广度观察"), index=0)
            theme_mode = "breadth" if theme_mode_label == "广度观察" else "representative"
        sector_type = st.selectbox("板块类型", SECTOR_TYPES, index=SECTOR_TYPES.index(DEFAULT_SECTOR_TYPE))
        refresh_interval = st.selectbox(
            "刷新间隔",
            (15, 30, 60),
            index=(15, 30, 60).index(REFRESH_INTERVAL_SECONDS),
        )
        top_in = st.number_input("净流入 Top N", min_value=1, max_value=30, value=DEFAULT_TOP_IN, step=1)
        top_out = st.number_input("净流出 Top N", min_value=1, max_value=40, value=DEFAULT_TOP_OUT, step=1)
        demo_mode = st.toggle("启用 DEMO 模式", value=False)
        st.caption("DEMO 仅用于 UI 调试，不代表真实行情。")

    st_autorefresh(interval=refresh_interval * 1000, key="fund_flow_refresh")

    now = get_china_now()
    trade_date = now.strftime("%Y-%m-%d")
    market_status = get_market_status(now)
    can_fetch = market_status in FETCH_ALLOWED_STATUSES
    error = None
    data_status = "CACHE"
    status_note = "暂无可用缓存"
    latest_label = "最新缓存"
    latest_status_time = None

    if demo_mode:
        ticks_df = _make_demo_data(sector_type, now)
        data_status = "DEMO"
        status_note = "模拟数据，仅用于 UI 调试，不代表真实行情。"
        latest_label = "模拟时间"
    else:
        if can_fetch:
            try:
                raw = fetch_sector_flow(sector_type=sector_type, indicator="今日")
                snapshot = normalize_sector_flow(raw, sector_type=sector_type, captured_at=now)
                append_snapshot(snapshot)
                data_status = "LIVE"
                status_note = "实时抓取成功"
                latest_label = "最新更新时间"
                latest_status_time = snapshot["captured_time"].iloc[0] if not snapshot.empty else now.strftime("%H:%M:%S")
            except RuntimeError as exc:
                error = str(exc)
                data_status = "CACHE"
                status_note = "本轮抓取失败，当前展示最近缓存"
                latest_label = "最新缓存"
        else:
            data_status = "CACHE"
            status_note = "非交易时间，当前展示最近缓存"
            latest_label = "最新缓存"

        if data_status == "LIVE":
            ticks_df = _filter_sector_type(load_today_ticks(trade_date), sector_type)
        else:
            ticks_df = _load_cache_ticks(trade_date, sector_type)

    has_display_cache = (not demo_mode) and (not ticks_df.empty)
    if data_status == "CACHE" and not has_display_cache:
        status_note = "暂无可用缓存"

    latest_time = _latest_time(ticks_df, now.strftime("%H:%M:%S"))
    if latest_status_time is None:
        latest_status_time = latest_time
    header_date = trade_date
    if not ticks_df.empty and "trade_date" in ticks_df.columns:
        header_date = str(ticks_df["trade_date"].dropna().iloc[-1])

    display_ticks_df = ticks_df
    if display_mode == "基金观察池":
        display_ticks_df = apply_theme_pool_to_ticks(ticks_df, theme_mode=theme_mode)

    render_header(header_date, latest_time)
    extra_status = f"主题口径：{theme_mode_label}" if display_mode == "基金观察池" else None
    render_status_bar(
        market_status=market_status,
        refresh_interval=refresh_interval,
        data_status=data_status,
        status_note=status_note,
        sector_type=sector_type,
        latest_label=latest_label,
        latest_time=latest_status_time,
        extra_text=extra_status,
    )
    if display_mode == "基金观察池":
        note = (
            "代表口径：优先使用主题核心板块，降低上下级板块重复计数风险。"
            if theme_mode == "representative"
            else "广度观察：聚合更多相关板块，用于观察主题热度，数值可能包含相关板块重叠，不代表严格净流入。"
        )
        st.markdown(
            f"<div class='small-note'>基金观察池会将相近行业/概念归并为基金主题，仅用于辅助观察。{note}</div>",
            unsafe_allow_html=True,
        )
    if not can_fetch and not demo_mode and has_display_cache:
        st.caption("非交易时间，展示最近缓存数据。")
    render_error_box(error, has_cache=has_display_cache)

    fig = build_flow_chart(display_ticks_df, top_in=int(top_in), top_out=int(top_out))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    latest_df = _latest_snapshot(display_ticks_df)
    render_rank_tables(latest_df)

    with st.expander("数据说明", expanded=False):
        st.write(
            "第一版使用 AKShare 获取东方财富板块资金流排名数据，页面每次 rerun 抓取并保存 CSV 快照。"
            "本项目仅用于学习和可视化，不构成投资建议。"
        )
        st.code("data/ticks/sector_flow_YYYY-MM-DD.csv")


if __name__ == "__main__":
    main()
