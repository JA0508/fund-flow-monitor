from __future__ import annotations

import math

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src.chart import build_flow_chart
from src.concept_flow import (
    CONCEPT_SECTOR_TYPE,
    get_concept_cache_summary,
    get_concept_latest_snapshot,
    should_refresh_concept_cache,
    summarize_concept_hotspots,
)
from src.config import (
    APP_CN_NAME,
    DEFAULT_SECTOR_TYPE,
    DEFAULT_TOP_IN,
    DEFAULT_TOP_OUT,
    FETCH_ALLOWED_STATUSES,
    REFRESH_INTERVAL_SECONDS,
    SECTOR_TYPES,
    TIMEZONE,
)
from src.data_source import fetch_sector_flow
from src.fund_profiles import (
    build_fund_summary,
    build_fund_theme_exposure,
    build_holding_related_pool,
    get_funds,
    load_fund_profiles,
    validate_fund_profile,
)
from src.intraday_hotspots import (
    build_intraday_hotspot_pool,
    build_intraday_hotspot_summary,
    build_theme_intraday_history,
    calculate_intraday_theme_metrics,
    split_hotspot_sections,
)
from src.market_time import get_market_status
from src.snapshot_catalog import (
    build_snapshot_catalog,
    get_latest_snapshot_date,
    get_snapshot_summary,
    infer_view_data_status,
    load_snapshot_by_date,
)
from src.storage import append_snapshot, load_latest_ticks, load_today_ticks
from src.theme_concepts import build_theme_concept_summary
from src.theme_pool import apply_theme_pool_to_ticks, build_theme_snapshot
from src.theme_radar import build_market_temperature, build_theme_radar_snapshot, compare_strict_and_breadth
from src.transform import normalize_sector_flow
from src.ui_components import (
    inject_global_css,
    render_divergence_cards,
    render_app_footer,
    render_concept_error_box,
    render_concept_hotspots,
    render_data_trust_panel,
    render_error_box,
    render_fund_profile_overview,
    render_fund_summary_cards,
    render_holding_related_table,
    render_header,
    render_hotspot_cards,
    render_intraday_hotspot_overview,
    render_intraday_hotspot_table,
    render_market_temperature_card,
    render_rank_tables,
    render_snapshot_catalog_table,
    render_status_bar,
    render_theme_concept_cards,
    render_theme_radar_cards,
)
from src.utils import get_china_now
from src.watchlist import filter_watchlist_theme_df, get_watchlist_themes, load_watchlist


st.set_page_config(
    page_title=APP_CN_NAME,
    page_icon=":material/query_stats:",
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

    now = get_china_now()
    trade_date = now.strftime("%Y-%m-%d")
    market_status = get_market_status(now)
    can_fetch = market_status in FETCH_ALLOWED_STATUSES
    snapshot_catalog_df = build_snapshot_catalog()
    latest_snapshot_date = get_latest_snapshot_date(snapshot_catalog_df)

    with st.sidebar:
        st.header("监测设置")
        st.markdown("### 数据日期 / 历史回放")
        date_mode = st.selectbox(
            "数据日期",
            ("自动使用最新缓存", "选择历史日期"),
            index=0,
            key="snapshot_date_mode",
        )
        history_mode_requested = date_mode == "选择历史日期"
        selected_snapshot_date = trade_date if can_fetch else (latest_snapshot_date or trade_date)
        if history_mode_requested:
            if snapshot_catalog_df.empty:
                st.caption("暂无本地 CSV 快照。")
                selected_snapshot_date = None
            else:
                options = snapshot_catalog_df["snapshot_date"].astype(str).tolist()
                current_history_date = st.session_state.get("selected_history_snapshot_date")
                history_index = options.index(current_history_date) if current_history_date in options else 0
                labels = {
                    row["snapshot_date"]: (
                        f"{row['snapshot_date']} · {int(row['captured_time_count'])} 个时间点 · {row['quality_label']}"
                    )
                    for _, row in snapshot_catalog_df.iterrows()
                }
                selected_snapshot_date = st.selectbox(
                    "选择缓存日期",
                    options,
                    format_func=lambda value: labels.get(value, value),
                    index=history_index,
                    key="selected_history_snapshot_date",
                )
        elif latest_snapshot_date and not can_fetch:
            st.caption(f"非交易时间自动展示最新缓存：{latest_snapshot_date}")

        display_mode = st.selectbox("展示模式", ("基金观察池", "原始板块"), index=0)
        theme_mode_label = None
        theme_mode = "strict_representative"
        if display_mode == "基金观察池":
            theme_mode_label = st.selectbox("主题口径", ("严格代表口径", "代表口径", "广度观察"), index=0)
            theme_mode = {
                "严格代表口径": "strict_representative",
                "代表口径": "representative",
                "广度观察": "breadth",
            }[theme_mode_label]
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
        st.markdown("### 概念资金流辅助")
        concept_assist_enabled = st.toggle("启用概念资金流辅助", value=False)
        concept_manual_refresh = False
        if concept_assist_enabled:
            concept_manual_refresh = st.button("刷新概念资金流", type="secondary")
            st.caption("概念资金流低频刷新，用于主题热度辅助观察。")

    st_autorefresh(interval=refresh_interval * 1000, key="fund_flow_refresh")
    error = None
    concept_error = None
    data_status = "CACHE"
    concept_data_status = "CONCEPT_EMPTY"
    concept_status_note = "概念资金流辅助未启用"
    status_note = "暂无可用缓存"
    latest_label = "最新缓存"
    latest_status_time = None
    is_history_replay = bool(
        not demo_mode
        and (
            history_mode_requested
            or (selected_snapshot_date and selected_snapshot_date != trade_date)
        )
    )

    if demo_mode:
        ticks_df = _make_demo_data(sector_type, now)
        all_ticks_df = ticks_df.copy()
        data_status = "DEMO"
        concept_data_status = "CONCEPT_EMPTY"
        status_note = "模拟数据，仅用于 UI 调试，不代表真实行情。"
        concept_status_note = "DEMO 模式下不抓取概念资金流"
        latest_label = "模拟时间"
    elif is_history_replay:
        all_ticks_df = load_snapshot_by_date(selected_snapshot_date)
        ticks_df = _filter_sector_type(all_ticks_df, sector_type)
        data_status = "HISTORY" if not all_ticks_df.empty else "EMPTY"
        status_note = (
            "历史回放模式，当前展示本地 CSV 缓存，不代表实时行情。"
            if not all_ticks_df.empty
            else "暂无可用真实缓存，可等待抓取或启用 DEMO 测试 UI。"
        )
        latest_label = "回放时间"
        concept_summary = get_concept_cache_summary(all_ticks_df)
        if concept_summary.get("has_concept_cache"):
            concept_data_status = "CONCEPT_CACHE"
            concept_status_note = "历史回放中的概念缓存"
        else:
            concept_data_status = "CONCEPT_EMPTY"
            concept_status_note = "该日期暂无概念资金流缓存"
    else:
        is_concept_main = sector_type == CONCEPT_SECTOR_TYPE
        all_ticks_df = load_today_ticks(trade_date)
        concept_summary = get_concept_cache_summary(all_ticks_df)
        concept_refresh_due = should_refresh_concept_cache(
            concept_summary.get("latest_concept_captured_at"),
            now,
            max_age_minutes=5,
        )
        last_concept_attempt_at = st.session_state.get("last_concept_attempt_at")
        concept_attempt_due = should_refresh_concept_cache(last_concept_attempt_at, now, max_age_minutes=5)
        concept_should_fetch = (
            (concept_assist_enabled or is_concept_main)
            and can_fetch
            and (
                concept_manual_refresh
                or ((not concept_summary.get("has_concept_cache") or concept_refresh_due) and concept_attempt_due)
            )
        )

        if can_fetch and not is_concept_main:
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
        elif is_concept_main:
            data_status = "CACHE"
            status_note = "概念资金流采用低频策略，当前展示概念缓存"
            latest_label = "最新缓存"
        else:
            data_status = "CACHE"
            status_note = "非交易时间，当前展示最近缓存"
            latest_label = "最新缓存"

        if concept_should_fetch:
            st.session_state["last_concept_attempt_at"] = now
            try:
                raw_concept = fetch_sector_flow(sector_type=CONCEPT_SECTOR_TYPE, indicator="今日")
                concept_snapshot = normalize_sector_flow(
                    raw_concept,
                    sector_type=CONCEPT_SECTOR_TYPE,
                    captured_at=now,
                )
                append_snapshot(concept_snapshot)
                concept_data_status = "CONCEPT_LIVE"
                concept_status_note = "概念资金流低频抓取成功"
                if is_concept_main:
                    data_status = "LIVE"
                    status_note = "概念资金流低频抓取成功"
                    latest_label = "最新更新时间"
                    latest_status_time = (
                        concept_snapshot["captured_time"].iloc[0]
                        if not concept_snapshot.empty
                        else now.strftime("%H:%M:%S")
                    )
                all_ticks_df = load_today_ticks(trade_date)
            except RuntimeError as exc:
                concept_error = str(exc)
                concept_data_status = "CONCEPT_ERROR"
                concept_status_note = "概念资金流抓取失败，保留行业主链路"

        concept_summary = get_concept_cache_summary(all_ticks_df)
        if concept_data_status != "CONCEPT_LIVE":
            if concept_data_status == "CONCEPT_ERROR":
                pass
            elif concept_summary.get("has_concept_cache"):
                concept_data_status = "CONCEPT_CACHE"
                concept_status_note = (
                    "概念缓存较旧，可手动刷新。"
                    if should_refresh_concept_cache(concept_summary.get("latest_concept_captured_at"), now, 5)
                    else "当前展示最近概念缓存"
                )
            else:
                concept_data_status = "CONCEPT_EMPTY"
                concept_status_note = (
                    "暂无概念资金流缓存，可点击刷新。"
                    if concept_assist_enabled or is_concept_main
                    else "概念资金流辅助未启用"
                )

        if data_status == "LIVE":
            ticks_df = _filter_sector_type(load_today_ticks(trade_date), sector_type)
        else:
            ticks_df = _load_cache_ticks(trade_date, sector_type)
        if is_concept_main:
            ticks_df = _filter_sector_type(all_ticks_df, CONCEPT_SECTOR_TYPE)

    has_display_cache = (not demo_mode) and (not ticks_df.empty)
    if data_status == "CACHE" and not has_display_cache:
        status_note = "暂无可用缓存"
    active_summary = get_snapshot_summary(all_ticks_df)
    if not demo_mode and active_summary["row_count"] == 0:
        data_status = "EMPTY"
        status_note = "暂无可用真实缓存，可等待抓取或启用 DEMO 测试 UI。"
    view_status = infer_view_data_status(
        selected_snapshot_date or "",
        trade_date,
        data_status,
        demo_mode,
        history_mode_requested=history_mode_requested,
    )
    if view_status == "HISTORY":
        data_status = "HISTORY"
        status_note = "历史回放模式，当前展示本地 CSV 缓存，不代表实时行情。"
    elif view_status == "EMPTY":
        data_status = "EMPTY"

    latest_time = _latest_time(ticks_df, now.strftime("%H:%M:%S"))
    if ticks_df.empty and active_summary.get("latest_captured_time"):
        latest_time = str(active_summary["latest_captured_time"])
    if latest_status_time is None:
        latest_status_time = latest_time
    header_date = selected_snapshot_date or trade_date
    if not ticks_df.empty and "trade_date" in ticks_df.columns:
        header_date = str(ticks_df["trade_date"].dropna().iloc[-1])

    selected_catalog_row = pd.DataFrame()
    if not snapshot_catalog_df.empty and selected_snapshot_date:
        selected_catalog_row = snapshot_catalog_df[snapshot_catalog_df["snapshot_date"].astype(str).eq(str(selected_snapshot_date))]
    quality_label = selected_catalog_row["quality_label"].iloc[0] if not selected_catalog_row.empty else (
        "DEMO" if demo_mode else "EMPTY"
    )

    display_ticks_df = ticks_df
    if display_mode == "基金观察池":
        display_ticks_df = apply_theme_pool_to_ticks(ticks_df, theme_mode=theme_mode)
        display_ticks_df = build_theme_radar_snapshot(display_ticks_df)

    fig = build_flow_chart(display_ticks_df, top_in=int(top_in), top_out=int(top_out))
    latest_df = _latest_snapshot(display_ticks_df)
    raw_latest_df = _latest_snapshot(ticks_df)
    concept_cache_summary = get_concept_cache_summary(all_ticks_df)
    concept_latest_df = get_concept_latest_snapshot(all_ticks_df)
    concept_hotspots_df = summarize_concept_hotspots(concept_latest_df, top_n=10)
    radar_theme_df = latest_df
    if display_mode != "基金观察池":
        radar_theme_df = build_theme_snapshot(raw_latest_df, theme_mode="strict_representative")
    watchlist = load_watchlist()
    watchlist_themes = get_watchlist_themes(watchlist)
    concept_summary_df = pd.DataFrame()
    if concept_assist_enabled and not concept_latest_df.empty:
        concept_summary_df = build_theme_concept_summary(concept_latest_df, watchlist_themes)
    radar_theme_df = build_theme_radar_snapshot(
        radar_theme_df,
        concept_summary_df=concept_summary_df if concept_assist_enabled else None,
    )
    strict_theme_df = build_theme_snapshot(raw_latest_df, theme_mode="strict_representative")
    breadth_theme_df = build_theme_snapshot(raw_latest_df, theme_mode="breadth")
    divergence_df = compare_strict_and_breadth(strict_theme_df, breadth_theme_df)
    watchlist_radar_df = filter_watchlist_theme_df(radar_theme_df, watchlist_themes)
    watchlist_divergence_df = filter_watchlist_theme_df(divergence_df, watchlist_themes)
    watchlist_concept_df = filter_watchlist_theme_df(concept_summary_df, watchlist_themes)
    fund_profile = load_fund_profiles()
    fund_profile_warnings = validate_fund_profile(fund_profile)
    fund_exposure_df = build_fund_theme_exposure(get_funds(fund_profile))
    holding_pool_df = build_holding_related_pool(fund_exposure_df, radar_theme_df)
    fund_summary_df = build_fund_summary(holding_pool_df)
    intraday_mode = theme_mode if display_mode == "基金观察池" else "breadth"
    intraday_history_df = build_theme_intraday_history(all_ticks_df, mode=intraday_mode)
    intraday_snapshot_count = (
        intraday_history_df["captured_time"].nunique()
        if not intraday_history_df.empty and "captured_time" in intraday_history_df.columns
        else 0
    )
    intraday_metrics_df = calculate_intraday_theme_metrics(intraday_history_df)
    intraday_hotspot_pool_df = build_intraday_hotspot_pool(intraday_metrics_df, top_n=12)
    intraday_sections = split_hotspot_sections(intraday_hotspot_pool_df)
    intraday_summary = build_intraday_hotspot_summary(intraday_hotspot_pool_df)
    snapshot_count = int(active_summary.get("row_count", 0) or 0)
    captured_time_count = int(active_summary.get("captured_time_count", 0) or 0)
    extra_status = f"主题口径：{theme_mode_label}" if display_mode == "基金观察池" else None
    theme_note = None
    if display_mode == "基金观察池":
        theme_note = (
            "严格代表口径：只使用主题核心板块的精确匹配，最克制，适合默认观察。"
            if theme_mode == "strict_representative"
            else (
                "代表口径：优先使用核心板块，必要时使用近似板块补充。"
                if theme_mode == "representative"
                else "广度观察：聚合更多相关板块，用于观察主题热度，可能包含上下级重叠，不代表严格净流入。"
            )
        )

    render_header(header_date, latest_time)
    tab_curve, tab_radar, tab_intraday, tab_holdings, tab_rank, tab_data = st.tabs(
        ("实时曲线", "主题雷达", "日内热点", "持仓相关池", "排行榜", "数据说明")
    )

    with tab_curve:
        render_status_bar(
            market_status=market_status,
            refresh_interval=refresh_interval,
            data_status=data_status,
            status_note=status_note,
            sector_type=sector_type,
            latest_label=latest_label,
            latest_time=latest_status_time,
            extra_text=extra_status,
            selected_snapshot_date=selected_snapshot_date,
            captured_time_count=captured_time_count,
            quality_label=quality_label,
        )
        if theme_note:
            st.markdown(
                f"<div class='small-note'>基金观察池会将相近行业/概念归并为基金主题，仅用于辅助观察。{theme_note}</div>",
                unsafe_allow_html=True,
            )
        if data_status == "HISTORY":
            st.caption("历史回放模式不会触发 AKShare 抓取，也不会写入 CSV。")
        elif data_status == "EMPTY":
            st.caption("暂无可用真实缓存，可等待抓取或启用 DEMO 测试 UI。")
        elif not can_fetch and not demo_mode and has_display_cache:
            st.caption("非交易时间，展示最近缓存数据。")
        render_error_box(error, has_cache=has_display_cache)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.markdown(
            "<div class='small-note'>主图展示当前净流入 Top 与净流出 Top 的日内时间序列；缓存和模拟状态会在状态条中明确标记。</div>",
            unsafe_allow_html=True,
        )

    with tab_radar:
        render_market_temperature_card(build_market_temperature(radar_theme_df))
        render_theme_radar_cards(watchlist_radar_df, max_cards=8)
        if concept_assist_enabled:
            st.markdown(
                f"<div class='small-note'>概念状态：{concept_data_status} ｜ {concept_status_note}。概念资金流用于辅助观察，不与行业资金流直接相加。</div>",
                unsafe_allow_html=True,
            )
            if concept_error:
                render_concept_error_box(concept_error, has_cache=concept_cache_summary.get("has_concept_cache", False))
            render_theme_concept_cards(watchlist_concept_df, max_cards=8)
        else:
            render_theme_concept_cards(pd.DataFrame(), max_cards=8)
        render_divergence_cards(watchlist_divergence_df, max_cards=5)

    with tab_intraday:
        st.markdown(
            f"<div class='concept-note'>本页基于所选数据日期 <b>{selected_snapshot_date or '--'}</b> 的本地 CSV 资金流快照，观察主题资金在日内的变化。"
            "结果仅用于解释已发生的资金流状态，不预测未来走势，不构成投资建议。</div>",
            unsafe_allow_html=True,
        )
        if intraday_snapshot_count < 2:
            st.markdown(
                "<div class='rank-panel'><div class='rank-empty'>当前快照数量不足，暂无法判断日内变化。请等待更多快照或继续使用实时曲线。</div></div>",
                unsafe_allow_html=True,
            )
        else:
            render_intraday_hotspot_overview(intraday_summary, snapshot_count=intraday_snapshot_count)
            render_hotspot_cards("流入/修复主题", intraday_sections["positive_hotspots"], max_cards=6)
            render_hotspot_cards("日内改善主题", intraday_sections["improving_hotspots"], max_cards=6)
            render_hotspot_cards("承压/走弱主题", intraday_sections["pressure_hotspots"], max_cards=6)
            with st.expander("分化观察主题", expanded=False):
                render_hotspot_cards("分化观察主题", intraday_sections["neutral_hotspots"], max_cards=6)
            render_intraday_hotspot_table(intraday_hotspot_pool_df, max_rows=30)

    with tab_holdings:
        st.markdown(
            f"<div class='concept-note'>本页基于 <code>config/fund_profiles.json</code> 中的手动主题配置，将关注基金/ETF 映射到所选日期 <b>{selected_snapshot_date or '--'}</b> 的主题资金状态。"
            "它不读取真实账户，也不代表真实基金持仓，不构成投资建议。</div>",
            unsafe_allow_html=True,
        )
        render_fund_profile_overview(fund_profile, fund_profile_warnings, fund_exposure_df)
        render_fund_summary_cards(fund_summary_df, max_cards=8)
        render_holding_related_table(holding_pool_df, max_rows=30)

    with tab_rank:
        render_rank_tables(latest_df)
        if concept_assist_enabled and not concept_hotspots_df.empty:
            render_concept_hotspots(concept_hotspots_df, max_rows=10)

    with tab_data:
        render_data_trust_panel(
            data_status=data_status,
            status_note=status_note,
            latest_label=latest_label,
            latest_time=latest_status_time,
            market_status=market_status,
            sector_type=sector_type,
            display_mode=display_mode,
            theme_mode_label=theme_mode_label,
            snapshot_count=snapshot_count,
            captured_time_count=captured_time_count,
            selected_snapshot_date=selected_snapshot_date,
            quality_label=quality_label,
        )
        st.markdown("#### 数据源说明")
        st.markdown(
            "- 第一版使用 AKShare 获取东方财富板块资金流排名数据。免费数据源可能受网络、上游接口和非交易时段影响。\n"
            "- 页面 rerun 时会按市场状态尝试抓取；抓取成功写入 CSV，失败则读取最近真实缓存。\n"
            "- CSV 路径：`data/ticks/sector_flow_YYYY-MM-DD.csv`。"
        )
        st.markdown("#### 历史快照回放")
        st.markdown(
            f"- 当前数据日期：`{selected_snapshot_date or '--'}`，视图状态：`{data_status}`。\n"
            "- HISTORY 表示历史回放，只读取所选日期本地 CSV 缓存，不代表实时行情。\n"
            "- 历史回放不会触发 AKShare 抓取，也不会写入 CSV。\n"
            "- EMPTY 表示暂无可用真实缓存，可等待正常抓取或启用 DEMO 进行 UI 测试。\n"
            "- 历史回放只用于观察已保存的资金流状态。"
        )
        render_snapshot_catalog_table(snapshot_catalog_df)
        st.markdown("#### 概念资金流辅助")
        st.markdown(
            f"- 概念辅助状态：`{concept_data_status}`，{concept_status_note}。\n"
            f"- 概念缓存：{concept_cache_summary.get('concept_rows', 0)} 行 / "
            f"{concept_cache_summary.get('concept_unique_times', 0)} 个时间点 / "
            f"最新 {concept_cache_summary.get('latest_concept_time') or '--:--:--'}。\n"
            "- 概念资金流采用低频策略：手动刷新、无缓存或缓存超过 5 分钟时才尝试抓取。\n"
            "- 概念资金流只用于观察主题热度和内部分化，不与行业资金流直接相加。"
        )
        st.markdown("#### 主题口径")
        st.markdown(
            "- 严格代表口径：只使用主题核心板块的精确匹配，最克制，适合默认观察。\n"
            "- 代表口径：优先使用核心板块，必要时使用近似板块补充。\n"
            "- 广度观察：聚合更多相关板块，用于观察主题热度，可能包含上下级重叠，不代表严格净流入。"
        )
        st.markdown("#### watchlist.json")
        st.markdown(
            "关注主题来自 `config/watchlist.json`，可以手动增删主题名称。配置缺失时会使用默认关注主题。"
        )
        st.markdown("#### fund_profiles.json")
        st.markdown(
            "持仓相关池来自 `config/fund_profiles.json` 的手动主题配置。它只表示你想观察的基金/ETF 与主题暴露关系，"
            "不读取真实账户，不代表真实基金持仓，也不预测基金净值。"
        )
        st.markdown("#### 日内热点池")
        st.markdown(
            f"- 日内热点池基于本地 CSV 中同一交易日的行业资金流快照，当前可用主题快照时间点：{intraday_snapshot_count}。\n"
            "- 它只解释已经发生的日内资金流变化、排名变化和流入/流出持续性。\n"
            "- captured_time 少于 2 时不会判断异动，只显示等待更多快照的提示。\n"
            "- 日内热点不是未来走势预测，也不构成投资建议。"
        )
        st.markdown("#### 免责声明")
        st.markdown(
            "本项目仅用于学习研究和可视化展示。资金温度、主题雷达和分歧提示只描述已观察到的资金流状态，"
            "不提供交易功能，不预测未来走势，不构成投资建议。"
        )

    render_app_footer()


if __name__ == "__main__":
    main()
