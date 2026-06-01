from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from src.config import DATA_SOURCE
from src.utils import format_billion


STATUS_TEXT = {
    "pre_open": "集合竞价",
    "trading_morning": "交易中",
    "lunch_break": "午间休市",
    "trading_afternoon": "交易中",
    "closed": "已收盘",
    "weekend": "非交易时间",
}


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #050505; color: #e5e7eb; }
        [data-testid="stSidebar"] { background: #0b0b0b; }
        [data-testid="stHeader"] { background: rgba(5, 5, 5, 0); }
        .block-container { padding-top: .7rem; max-width: 1720px; }
        .main-title { text-align: center; font-size: 31px; font-weight: 800; margin: 0; color: #f0c65a; line-height: 1.15; }
        .time-title { text-align: center; font-size: 22px; color: #26e07f; margin: 0.15rem 0 0.45rem; font-weight: 750; line-height: 1.15; }
        .compact-status { border: 1px solid rgba(255,255,255,.12); background: #080808; color: #d1d5db; padding: 8px 12px; border-radius: 8px; font-size: 13px; line-height: 1.7; margin: 0.2rem 0 0.45rem; text-align: center; }
        .compact-status b { color: #f3f4f6; font-weight: 750; }
        .status-live { color: #26e07f; font-weight: 850; }
        .status-cache { color: #60a5fa; font-weight: 850; }
        .status-demo { color: #ffd166; font-weight: 850; }
        .small-note { color: #9ca3af; font-size: 13px; margin: 0.15rem 0 0.4rem; text-align: center; }
        .demo-alert { border: 1px solid rgba(255, 179, 0, .55); background: rgba(255, 179, 0, .10); color: #ffd166; padding: 8px 12px; border-radius: 8px; margin: 4px 0 8px; text-align: center; font-weight: 800; letter-spacing: .02em; }
        .cache-alert { border: 1px solid rgba(96, 165, 250, .25); background: rgba(37, 99, 235, .08); color: #bfdbfe; padding: 8px 12px; border-radius: 8px; margin: 4px 0 8px; font-size: 13px; }
        .error-box { border: 1px solid rgba(248,113,113,.45); background: rgba(127,29,29,.35); color: #fecaca; padding: 10px 12px; border-radius: 8px; margin: 8px 0; }
        .rank-title { font-size: 17px; font-weight: 800; margin: 6px 0 8px; }
        .rank-panel { background: #080808; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; overflow: hidden; }
        .rank-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .rank-table thead { background: #111827; color: #aab2c0; }
        .rank-table th { text-align: left; padding: 9px 10px; font-weight: 700; border-bottom: 1px solid rgba(255,255,255,.08); }
        .rank-table td { padding: 8px 10px; color: #d1d5db; border-bottom: 1px solid rgba(255,255,255,.055); }
        .rank-table tr:nth-child(even) td { background: #0b0f14; }
        .rank-table tr:hover td { background: #111827; }
        .amount-in { color: #ffb703 !important; font-weight: 800; }
        .amount-out { color: #2ec4b6 !important; font-weight: 800; }
        .rank-empty { color: #8b949e; padding: 18px; }
        .radar-section-title { font-size: 19px; font-weight: 850; margin: 14px 0 8px; color: #e5e7eb; }
        .temperature-grid { display: grid; grid-template-columns: 1.35fr repeat(4, minmax(0, .8fr)); gap: 10px; margin: 8px 0 12px; }
        .radar-card { background: #080808; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; padding: 12px 14px; min-height: 116px; }
        .radar-card-title { color: #f3f4f6; font-size: 16px; font-weight: 850; margin-bottom: 8px; }
        .radar-card-label { color: #8b949e; font-size: 12px; }
        .radar-card-value { color: #e5e7eb; font-size: 20px; font-weight: 850; margin: 2px 0 4px; }
        .radar-reason { color: #aab2c0; font-size: 12.5px; line-height: 1.55; margin-top: 8px; }
        .radar-meta { color: #8b949e; font-size: 12px; line-height: 1.5; }
        .radar-positive-strong, .radar-positive-weak { color: #ffb703 !important; }
        .radar-negative-strong, .radar-negative-weak { color: #2ec4b6 !important; }
        .radar-neutral { color: #c9d1d9 !important; }
        .divergence-card { background: #080808; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; padding: 11px 13px; margin-bottom: 8px; }
        .divergence-title { color: #f0c65a; font-size: 14px; font-weight: 800; margin-bottom: 5px; }
        .divergence-body { color: #aab2c0; font-size: 12.5px; line-height: 1.5; }
        pre, code { background: #0b0f14 !important; color: #d1d5db !important; border-color: rgba(255,255,255,.08) !important; }
        @media (max-width: 900px) { .main-title { font-size: 25px; } .compact-status { text-align: left; } .temperature-grid { grid-template-columns: 1fr 1fr; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(trade_date: str, latest_time: str | None) -> None:
    dt = pd.Timestamp(trade_date)
    st.markdown(
        f"<div class='main-title'>{dt.month}月{dt.day}日 主力资金净流入</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='time-title'>◷ {latest_time or '--:--:--'}</div>",
        unsafe_allow_html=True,
    )


def render_status_bar(
    market_status: str,
    refresh_interval: int,
    data_status: str,
    status_note: str,
    sector_type: str,
    latest_label: str,
    latest_time: str | None,
    extra_text: str | None = None,
) -> None:
    market_text = STATUS_TEXT.get(market_status, market_status)
    status_class = {
        "LIVE": "status-live",
        "CACHE": "status-cache",
        "DEMO": "status-demo",
    }.get(data_status, "")
    html = (
        "<div class='compact-status'>"
        f"数据源：<b>{escape(DATA_SOURCE)}</b> ｜ "
        f"数据状态：<span class='{status_class}'>{escape(data_status)}</span> ｜ "
        f"状态说明：<b>{escape(status_note)}</b> ｜ "
        f"市场状态：<b>{escape(market_text)}</b> ｜ "
        f"{escape(latest_label)}：<b>{escape(latest_time or '--:--:--')}</b> ｜ "
        f"刷新：<b>{refresh_interval}秒</b> ｜ "
        f"板块类型：<b>{escape(sector_type)}</b>"
        f"{f' ｜ {escape(extra_text)}' if extra_text else ''}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    if data_status == "DEMO":
        st.markdown(
            "<div class='demo-alert'>DEMO MODE - 当前为模拟数据，不是真实行情</div>",
            unsafe_allow_html=True,
        )


def _shorten_sectors(value: object, max_items: int = 4) -> str:
    if value is None or pd.isna(value):
        return "--"
    sectors = [item.strip() for item in str(value).replace(",", "，").split("，") if item.strip()]
    if not sectors:
        return "--"
    if len(sectors) <= max_items:
        return "，".join(sectors)
    return "，".join(sectors[:max_items]) + f" 等 {len(sectors)} 个"


def filter_rank_rows(df: pd.DataFrame, direction: str, limit: int = 15) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    work = df.copy()
    work["main_net_inflow_billion"] = pd.to_numeric(work["main_net_inflow_billion"], errors="coerce")
    if direction == "in":
        work = work[work["main_net_inflow_billion"].gt(0)].sort_values("main_net_inflow_billion", ascending=False)
    else:
        work = work[work["main_net_inflow_billion"].lt(0)].sort_values("main_net_inflow_billion", ascending=True)
    return work.head(limit)


def _rank_table(df: pd.DataFrame, direction: str) -> pd.DataFrame:
    columns = ["排名", "主题/板块", "主力净流入", "状态", "涨跌幅", "净占比", "口径", "使用板块", "_source_sectors"]
    sorted_df = filter_rank_rows(df, direction=direction, limit=15)
    if sorted_df.empty:
        return pd.DataFrame(columns=columns)
    view = pd.DataFrame(
        {
            "排名": range(1, len(sorted_df) + 1),
            "主题/板块": sorted_df["sector_name"].values,
            "主力净流入": sorted_df["main_net_inflow_billion"].map(format_billion).values,
            "状态": sorted_df.get("theme_status", pd.Series(["--"] * len(sorted_df), index=sorted_df.index)).fillna("--").values,
            "涨跌幅": sorted_df["change_pct"].map(lambda x: "--" if pd.isna(x) else f"{x:.2f}%").values,
            "净占比": sorted_df["main_net_ratio"].map(lambda x: "--" if pd.isna(x) else f"{x:.2f}%").values,
            "口径": sorted_df.get("theme_value_label", pd.Series(["原始板块"] * len(sorted_df), index=sorted_df.index)).fillna("原始板块").values,
            "使用板块": sorted_df.get("used_sectors", sorted_df["sector_name"]).map(_shorten_sectors).values,
            "_source_sectors": sorted_df.get("source_sectors", sorted_df["sector_name"]).fillna("").astype(str).values,
        }
    )
    return view


def _render_html_table(df: pd.DataFrame, amount_class: str, empty_message: str) -> str:
    if df.empty:
        return f"<div class='rank-panel'><div class='rank-empty'>{escape(empty_message)}</div></div>"
    headers = ["排名", "主题/板块", "主力净流入", "状态", "涨跌幅", "净占比", "口径", "使用板块"]
    rows = []
    for _, row in df.iterrows():
        cells = []
        source_title = escape(str(row.get("_source_sectors", "")))
        for header in headers:
            class_name = f" class='{amount_class}'" if header == "主力净流入" else ""
            title = f" title='来源板块：{source_title}'" if header in {"主题/板块", "使用板块"} and source_title else ""
            cells.append(f"<td{class_name}{title}>{escape(str(row[header]))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    return (
        "<div class='rank-panel'>"
        "<table class='rank-table'>"
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>"
    )


def render_rank_tables(latest_df: pd.DataFrame) -> None:
    st.markdown("### 资金流排行榜")
    col_in, col_out = st.columns(2)
    inflow = _rank_table(latest_df, direction="in")
    outflow = _rank_table(latest_df, direction="out")
    with col_in:
        st.markdown("<div class='rank-title' style='color:#ffb703'>今日净流入榜</div>", unsafe_allow_html=True)
        st.markdown(_render_html_table(inflow, "amount-in", "暂无净流入主题/板块"), unsafe_allow_html=True)
    with col_out:
        st.markdown("<div class='rank-title' style='color:#2ec4b6'>今日净流出榜</div>", unsafe_allow_html=True)
        st.markdown(_render_html_table(outflow, "amount-out", "暂无净流出主题/板块"), unsafe_allow_html=True)


def _status_class(level: object) -> str:
    value = str(level or "")
    if value in {"positive_strong", "positive_weak"}:
        return "radar-positive-strong"
    if value in {"negative_strong", "negative_weak"}:
        return "radar-negative-strong"
    return "radar-neutral"


def render_market_temperature_card(temperature: dict) -> None:
    st.markdown("<div class='radar-section-title'>今日资金温度</div>", unsafe_allow_html=True)
    html = (
        "<div class='temperature-grid'>"
        "<div class='radar-card'>"
        "<div class='radar-card-label'>市场温度</div>"
        f"<div class='radar-card-value'>{escape(str(temperature.get('market_temperature_label', '--')))}</div>"
        f"<div class='radar-reason'>{escape(str(temperature.get('market_temperature_reason', '')))}</div>"
        "</div>"
        f"<div class='radar-card'><div class='radar-card-label'>流入主题数</div><div class='radar-card-value radar-positive-weak'>{int(temperature.get('positive_count', 0))}</div></div>"
        f"<div class='radar-card'><div class='radar-card-label'>流出主题数</div><div class='radar-card-value radar-negative-weak'>{int(temperature.get('negative_count', 0))}</div></div>"
        f"<div class='radar-card'><div class='radar-card-label'>强流入主题</div><div class='radar-card-value radar-positive-strong'>{int(temperature.get('strong_inflow_count', 0))}</div></div>"
        f"<div class='radar-card'><div class='radar-card-label'>强流出主题</div><div class='radar-card-value radar-negative-strong'>{int(temperature.get('strong_outflow_count', 0))}</div></div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_theme_radar_cards(radar_df: pd.DataFrame, max_cards: int = 8) -> None:
    st.markdown("<div class='radar-section-title'>关注主题雷达</div>", unsafe_allow_html=True)
    if radar_df is None or radar_df.empty:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>当前关注主题暂无可用资金流快照。</div></div>", unsafe_allow_html=True)
        return
    cards = radar_df.head(max_cards).to_dict("records")
    cols = st.columns(3)
    for idx, row in enumerate(cards):
        level_class = _status_class(row.get("theme_status_level"))
        amount = format_billion(row.get("main_net_inflow_billion"))
        used = _shorten_sectors(row.get("used_sectors"), max_items=4)
        html = (
            "<div class='radar-card'>"
            f"<div class='radar-card-title'>{escape(str(row.get('theme_name', '--')))}</div>"
            f"<div class='radar-card-value {level_class}'>{escape(amount)}</div>"
            f"<div class='radar-meta'>状态：<span class='{level_class}'>{escape(str(row.get('theme_status', '--')))}</span> ｜ {escape(str(row.get('radar_label', '--')))}</div>"
            f"<div class='radar-meta'>口径：{escape(str(row.get('theme_value_label', '--')))}</div>"
            f"<div class='radar-meta'>使用板块：{escape(used)}</div>"
            f"<div class='radar-reason'>{escape(str(row.get('radar_reason', '')))}</div>"
            "</div>"
        )
        with cols[idx % 3]:
            st.markdown(html, unsafe_allow_html=True)


def render_divergence_cards(divergence_df: pd.DataFrame, max_cards: int = 5) -> None:
    st.markdown("<div class='radar-section-title'>核心/广度分歧提示</div>", unsafe_allow_html=True)
    if divergence_df is None or divergence_df.empty:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>当前关注主题暂无明显核心/广度分歧。</div></div>", unsafe_allow_html=True)
        return
    priority_types = {
        "core_outflow_breadth_inflow",
        "core_inflow_breadth_outflow",
        "both_inflow",
        "both_outflow",
    }
    display_df = divergence_df[divergence_df["divergence_type"].isin(priority_types)].head(max_cards)
    if display_df.empty:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>当前关注主题暂无明显核心/广度分歧。</div></div>", unsafe_allow_html=True)
        return
    html = ""
    for _, row in display_df.iterrows():
        html += (
            "<div class='divergence-card'>"
            f"<div class='divergence-title'>{escape(str(row.get('theme_name', '--')))} ｜ {escape(str(row.get('divergence_type', '')))}</div>"
            f"<div class='divergence-body'>核心：{format_billion(row.get('strict_value'))}（{escape(str(row.get('strict_status', '--'))) }） ｜ "
            f"广度：{format_billion(row.get('breadth_value'))}（{escape(str(row.get('breadth_status', '--'))) }）</div>"
            f"<div class='divergence-body'>{escape(str(row.get('divergence_reason', '')))}</div>"
            "</div>"
        )
    st.markdown(html, unsafe_allow_html=True)


def render_error_box(error: str | None, has_cache: bool) -> None:
    if error:
        if has_cache:
            st.markdown(
                "<div class='cache-alert'>本轮 AKShare 请求失败，当前展示最近缓存数据。</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='error-box'>本轮 AKShare 请求失败，且本地暂无可用缓存。请运行 <code>python tools/probe_akshare.py</code> 检查接口。</div>",
                unsafe_allow_html=True,
            )
        with st.expander("查看错误详情", expanded=False, icon=":material/error:"):
            st.code(error)
