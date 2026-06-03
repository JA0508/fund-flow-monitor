from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from src.config import APP_CN_NAME, APP_VERSION, DATA_SOURCE
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
        .concept-card { background: #080808; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; padding: 11px 13px; min-height: 104px; margin-bottom: 8px; }
        .concept-title { color: #f3f4f6; font-size: 15px; font-weight: 850; margin-bottom: 6px; }
        .concept-status { color: #f0c65a; font-size: 13px; font-weight: 800; }
        .concept-body { color: #aab2c0; font-size: 12.5px; line-height: 1.55; }
        .concept-note { color: #9ca3af; border: 1px solid rgba(255,255,255,.08); background: #080808; padding: 10px 12px; border-radius: 8px; margin: 8px 0; font-size: 13px; }
        .holding-overview { display: grid; grid-template-columns: 1.4fr repeat(3, minmax(0, .8fr)); gap: 10px; margin: 8px 0 12px; }
        .holding-card { background: #080808; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; padding: 12px 14px; min-height: 118px; }
        .holding-title { color: #f3f4f6; font-size: 16px; font-weight: 850; margin-bottom: 8px; }
        .holding-value { color: #f0c65a; font-size: 20px; font-weight: 850; margin: 3px 0; }
        .holding-label { color: #8b949e; font-size: 12px; }
        .holding-body { color: #aab2c0; font-size: 12.5px; line-height: 1.55; margin-top: 6px; }
        .holding-warning { color: #ffd166; border: 1px solid rgba(255, 209, 102, .28); background: rgba(255, 209, 102, .08); padding: 9px 11px; border-radius: 8px; margin: 8px 0; font-size: 13px; }
        .hotspot-overview { display: grid; grid-template-columns: 1.35fr repeat(4, minmax(0, .8fr)); gap: 10px; margin: 8px 0 12px; }
        .hotspot-card { background: #080808; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; padding: 12px 14px; min-height: 118px; margin-bottom: 8px; }
        .hotspot-title { color: #f3f4f6; font-size: 16px; font-weight: 850; margin-bottom: 7px; }
        .hotspot-label { color: #f0c65a; font-size: 13px; font-weight: 850; }
        .hotspot-body { color: #aab2c0; font-size: 12.5px; line-height: 1.55; margin-top: 5px; }
        .hotspot-value { color: #e5e7eb; font-size: 19px; font-weight: 850; margin: 2px 0; }
        .trust-panel { background: #080808; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; padding: 14px 16px; margin: 8px 0 12px; }
        .trust-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 10px; }
        .trust-item { background: #0b0f14; border: 1px solid rgba(255,255,255,.06); border-radius: 8px; padding: 10px 12px; }
        .trust-label { color: #8b949e; font-size: 12px; margin-bottom: 4px; }
        .trust-value { color: #e5e7eb; font-size: 15px; font-weight: 800; }
        .trust-copy { color: #aab2c0; font-size: 13px; line-height: 1.65; margin-top: 8px; }
        .footer-note { color: #6b7280; text-align: center; font-size: 12px; margin: 18px 0 4px; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid rgba(255,255,255,.08); }
        .stTabs [data-baseweb="tab"] { background: #080808; border: 1px solid rgba(255,255,255,.08); border-bottom: 0; border-radius: 8px 8px 0 0; color: #aab2c0; padding: 8px 14px; }
        .stTabs [aria-selected="true"] { color: #f0c65a !important; background: #0b0f14 !important; }
        pre, code { background: #0b0f14 !important; color: #d1d5db !important; border-color: rgba(255,255,255,.08) !important; }
        @media (max-width: 900px) { .main-title { font-size: 25px; } .compact-status { text-align: left; } .temperature-grid { grid-template-columns: 1fr 1fr; } .trust-grid { grid-template-columns: 1fr; } .holding-overview { grid-template-columns: 1fr 1fr; } .hotspot-overview { grid-template-columns: 1fr 1fr; } }
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


def _format_rank_change(value: object) -> str:
    try:
        change = int(value)
    except (TypeError, ValueError):
        return "--"
    if change > 0:
        return f"上升 {change} 位"
    if change < 0:
        return f"回落 {abs(change)} 位"
    return "持平"


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
        concept_html = ""
        if "concept_status" in row and pd.notna(row.get("concept_status")):
            concept_html = (
                f"<div class='radar-meta'>相关概念：{escape(str(row.get('concept_status', '--')))} ｜ "
                f"{escape(format_billion(row.get('concept_net_inflow_billion')))}</div>"
            )
        html = (
            "<div class='radar-card'>"
            f"<div class='radar-card-title'>{escape(str(row.get('theme_name', '--')))}</div>"
            f"<div class='radar-card-value {level_class}'>{escape(amount)}</div>"
            f"<div class='radar-meta'>状态：<span class='{level_class}'>{escape(str(row.get('theme_status', '--')))}</span> ｜ {escape(str(row.get('radar_label', '--')))}</div>"
            f"<div class='radar-meta'>口径：{escape(str(row.get('theme_value_label', '--')))}</div>"
            f"<div class='radar-meta'>使用板块：{escape(used)}</div>"
            f"{concept_html}"
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


def render_theme_concept_cards(concept_summary_df: pd.DataFrame, max_cards: int = 8) -> None:
    st.markdown("<div class='radar-section-title'>相关概念热度</div>", unsafe_allow_html=True)
    if concept_summary_df is None or concept_summary_df.empty:
        st.markdown(
            "<div class='concept-note'>概念资金流辅助未启用，当前主题雷达仅基于行业资金流。</div>",
            unsafe_allow_html=True,
        )
        return
    cards = concept_summary_df.head(max_cards).to_dict("records")
    cols = st.columns(3)
    for idx, row in enumerate(cards):
        html = (
            "<div class='concept-card'>"
            f"<div class='concept-title'>{escape(str(row.get('theme_name', '--')))}</div>"
            f"<div class='concept-status'>{escape(str(row.get('concept_status', '--')))} ｜ {escape(format_billion(row.get('concept_net_inflow_billion')))}</div>"
            f"<div class='concept-body'>相关概念数：{int(row.get('related_concept_count', 0) or 0)}</div>"
            f"<div class='concept-body'>代表概念：{escape(_shorten_sectors(row.get('top_concepts'), max_items=4))}</div>"
            f"<div class='concept-body'>{escape(str(row.get('concept_reason', '')))}</div>"
            "</div>"
        )
        with cols[idx % 3]:
            st.markdown(html, unsafe_allow_html=True)


def render_concept_hotspots(hotspots_df: pd.DataFrame, max_rows: int = 10) -> None:
    st.markdown("<div class='radar-section-title'>概念热点观察</div>", unsafe_allow_html=True)
    if hotspots_df is None or hotspots_df.empty:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>暂无概念热点缓存。</div></div>", unsafe_allow_html=True)
        return
    headers = ["概念", "主力净流入", "涨跌幅", "净占比", "代表个股", "状态"]
    rows = []
    for _, row in hotspots_df.head(max_rows).iterrows():
        amount = row.get("main_net_inflow_billion")
        amount_class = "amount-in" if pd.to_numeric(pd.Series([amount]), errors="coerce").iloc[0] >= 0 else "amount-out"
        values = [
            row.get("concept_name", "--"),
            format_billion(amount),
            "--" if pd.isna(row.get("change_pct")) else f"{float(row.get('change_pct')):.2f}%",
            "--" if pd.isna(row.get("main_net_ratio")) else f"{float(row.get('main_net_ratio')):.2f}%",
            row.get("leading_stock", "--"),
            row.get("hotspot_status", "--"),
        ]
        cells = []
        for header, value in zip(headers, values, strict=False):
            class_name = f" class='{amount_class}'" if header == "主力净流入" else ""
            cells.append(f"<td{class_name}>{escape(str(value))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    html = (
        "<div class='rank-panel'>"
        "<table class='rank-table'>"
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_fund_profile_overview(profile: dict, warnings: list[str], exposure_df: pd.DataFrame) -> None:
    funds = profile.get("funds", []) if isinstance(profile, dict) else []
    matched_themes = exposure_df["theme_name"].nunique() if exposure_df is not None and not exposure_df.empty else 0
    html = (
        "<div class='radar-section-title'>基金组合概览</div>"
        "<div class='holding-overview'>"
        "<div class='holding-card'>"
        "<div class='holding-label'>配置名称</div>"
        f"<div class='holding-value'>{escape(str(profile.get('profile_name', '--')))}</div>"
        f"<div class='holding-body'>{escape(str(profile.get('description', '手动主题配置，不代表真实持仓。')))}</div>"
        "</div>"
        f"<div class='holding-card'><div class='holding-label'>基金/ETF 数量</div><div class='holding-value'>{len(funds)}</div></div>"
        f"<div class='holding-card'><div class='holding-label'>配置主题数</div><div class='holding-value'>{matched_themes}</div></div>"
        f"<div class='holding-card'><div class='holding-label'>配置提示</div><div class='holding-value'>{len(warnings)}</div><div class='holding-body'>warning 不会中断页面。</div></div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    if warnings:
        warning_html = "<br>".join(escape(str(item)) for item in warnings[:6])
        st.markdown(f"<div class='holding-warning'>{warning_html}</div>", unsafe_allow_html=True)


def render_fund_summary_cards(fund_summary_df: pd.DataFrame, max_cards: int = 8) -> None:
    st.markdown("<div class='radar-section-title'>基金摘要卡片</div>", unsafe_allow_html=True)
    if fund_summary_df is None or fund_summary_df.empty:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>暂无可用基金主题摘要。</div></div>", unsafe_allow_html=True)
        return
    cols = st.columns(2)
    for idx, row in enumerate(fund_summary_df.head(max_cards).to_dict("records")):
        score = float(row.get("weighted_impact_score", 0) or 0)
        score_class = "amount-in" if score > 0 else "amount-out" if score < 0 else "radar-neutral"
        html = (
            "<div class='holding-card'>"
            f"<div class='holding-title'>{escape(str(row.get('fund_name', '--')))}</div>"
            f"<div class='holding-body'>代码：{escape(str(row.get('fund_code', '--')))} ｜ 类型：{escape(str(row.get('fund_type', '--')))}</div>"
            f"<div class='holding-value {score_class}'>{score:.2f}</div>"
            f"<div class='holding-body'>状态：{escape(str(row.get('fund_impact_label', '--')))}</div>"
            f"<div class='holding-body'>偏强主题：{escape(str(row.get('top_positive_themes') or '暂无'))}</div>"
            f"<div class='holding-body'>承压主题：{escape(str(row.get('top_negative_themes') or '暂无'))}</div>"
            f"<div class='holding-body'>{escape(str(row.get('summary_reason', '')))}</div>"
            "</div>"
        )
        with cols[idx % 2]:
            st.markdown(html, unsafe_allow_html=True)


def render_holding_related_table(holding_pool_df: pd.DataFrame, max_rows: int = 30) -> None:
    st.markdown("<div class='radar-section-title'>主题暴露明细</div>", unsafe_allow_html=True)
    if holding_pool_df is None or holding_pool_df.empty:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>暂无持仓相关主题明细。</div></div>", unsafe_allow_html=True)
        return
    headers = ["基金", "主题", "权重", "主题状态", "主力净流入", "相关状态", "说明"]
    rows = []
    view = holding_pool_df.sort_values(["fund_name", "normalized_weight"], ascending=[True, False]).head(max_rows)
    for _, row in view.iterrows():
        amount = pd.to_numeric(pd.Series([row.get("main_net_inflow_billion")]), errors="coerce").iloc[0]
        amount_text = "--" if pd.isna(amount) else format_billion(amount)
        amount_class = "amount-in" if pd.notna(amount) and amount >= 0 else "amount-out"
        values = [
            row.get("fund_name", "--"),
            row.get("theme_name", "--"),
            f"{float(row.get('normalized_weight', 0) or 0):.1%}",
            row.get("theme_status", "--"),
            amount_text,
            row.get("holding_impact_label", "--"),
            row.get("holding_impact_reason", "--"),
        ]
        cells = []
        for header, value in zip(headers, values, strict=False):
            class_name = f" class='{amount_class}'" if header == "主力净流入" else ""
            cells.append(f"<td{class_name}>{escape(str(value))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    html = (
        "<div class='rank-panel'>"
        "<table class='rank-table'>"
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_intraday_hotspot_overview(summary: dict, snapshot_count: int) -> None:
    html = (
        "<div class='radar-section-title'>日内热点概览</div>"
        "<div class='hotspot-overview'>"
        "<div class='hotspot-card'>"
        "<div class='holding-label'>日内热点状态</div>"
        f"<div class='hotspot-value'>{escape(str(summary.get('summary_label', '--')))}</div>"
        f"<div class='hotspot-body'>{escape(str(summary.get('summary_reason', '')))}</div>"
        "</div>"
        f"<div class='hotspot-card'><div class='holding-label'>当前快照数量</div><div class='hotspot-value'>{int(snapshot_count or 0)}</div></div>"
        f"<div class='hotspot-card'><div class='holding-label'>覆盖主题数</div><div class='hotspot-value'>{int(summary.get('total_themes', 0) or 0)}</div></div>"
        f"<div class='hotspot-card'><div class='holding-label'>流入/修复</div><div class='hotspot-value amount-in'>{int(summary.get('positive_hotspot_count', 0) or 0)}</div></div>"
        f"<div class='hotspot-card'><div class='holding-label'>改善 / 承压 / 分化</div><div class='hotspot-value'>{int(summary.get('improving_count', 0) or 0)} / {int(summary.get('pressure_count', 0) or 0)} / {int(summary.get('neutral_count', 0) or 0)}</div></div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_hotspot_cards(title: str, hotspot_df: pd.DataFrame, max_cards: int = 6) -> None:
    st.markdown(f"<div class='radar-section-title'>{escape(title)}</div>", unsafe_allow_html=True)
    if hotspot_df is None or hotspot_df.empty:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>当前暂无该类日内热点。</div></div>", unsafe_allow_html=True)
        return
    cols = st.columns(3)
    for idx, row in enumerate(hotspot_df.head(max_cards).to_dict("records")):
        latest = format_billion(row.get("latest_value"))
        change = format_billion(row.get("value_change"))
        amount_class = "amount-in" if float(row.get("latest_value", 0) or 0) >= 0 else "amount-out"
        html = (
            "<div class='hotspot-card'>"
            f"<div class='hotspot-title'>{escape(str(row.get('theme_name', '--')))}</div>"
            f"<div class='hotspot-label'>{escape(str(row.get('hotspot_label', '--')))}</div>"
            f"<div class='hotspot-value {amount_class}'>{escape(latest)}</div>"
            f"<div class='hotspot-body'>变化：{escape(change)} ｜ 排名：{escape(_format_rank_change(row.get('rank_change')))}</div>"
            f"<div class='hotspot-body'>流入占比：{float(row.get('positive_ratio', 0) or 0):.0%} ｜ 流出占比：{float(row.get('negative_ratio', 0) or 0):.0%}</div>"
            f"<div class='hotspot-body'>状态：{escape(str(row.get('latest_status', '--')))} ｜ 来源数：{int(row.get('latest_source_count', 0) or 0)}</div>"
            f"<div class='hotspot-body'>来源：{escape(_shorten_sectors(row.get('latest_source_sectors'), max_items=4))}</div>"
            f"<div class='hotspot-body'>{escape(str(row.get('hotspot_reason', '')))}</div>"
            "</div>"
        )
        with cols[idx % 3]:
            st.markdown(html, unsafe_allow_html=True)


def render_intraday_hotspot_table(hotspot_pool_df: pd.DataFrame, max_rows: int = 30) -> None:
    st.markdown("<div class='radar-section-title'>日内变化明细</div>", unsafe_allow_html=True)
    if hotspot_pool_df is None or hotspot_pool_df.empty:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>暂无日内热点明细。</div></div>", unsafe_allow_html=True)
        return
    headers = ["主题", "热点标签", "最新金额", "日内变化", "排名变化", "流入占比", "流出占比", "最新状态", "说明"]
    rows = []
    for _, row in hotspot_pool_df.head(max_rows).iterrows():
        latest = float(row.get("latest_value", 0) or 0)
        amount_class = "amount-in" if latest >= 0 else "amount-out"
        values = [
            row.get("theme_name", "--"),
            row.get("hotspot_label", "--"),
            format_billion(row.get("latest_value")),
            format_billion(row.get("value_change")),
            _format_rank_change(row.get("rank_change")),
            f"{float(row.get('positive_ratio', 0) or 0):.0%}",
            f"{float(row.get('negative_ratio', 0) or 0):.0%}",
            row.get("latest_status", "--"),
            row.get("hotspot_reason", "--"),
        ]
        cells = []
        for header, value in zip(headers, values, strict=False):
            class_name = f" class='{amount_class}'" if header == "最新金额" else ""
            cells.append(f"<td{class_name}>{escape(str(value))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    html = (
        "<div class='rank-panel'>"
        "<table class='rank-table'>"
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
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


def render_concept_error_box(error: str | None, has_cache: bool) -> None:
    if error:
        if has_cache:
            st.markdown(
                "<div class='cache-alert'>本轮概念资金流请求失败，当前保留最近概念缓存；行业资金流主链路不受影响。</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='cache-alert'>本轮概念资金流请求失败，暂无概念缓存。可运行 <code>python tools/probe_concept_flow.py</code> 检查接口。</div>",
                unsafe_allow_html=True,
            )
        with st.expander("查看概念接口错误详情", expanded=False, icon=":material/error:"):
            st.code(error)


def render_data_trust_panel(
    *,
    data_status: str,
    status_note: str,
    latest_label: str,
    latest_time: str | None,
    market_status: str,
    sector_type: str,
    display_mode: str,
    theme_mode_label: str | None,
    snapshot_count: int,
    captured_time_count: int,
) -> None:
    market_text = STATUS_TEXT.get(market_status, market_status)
    theme_text = theme_mode_label if display_mode == "基金观察池" else "原始板块"
    status_class = {
        "LIVE": "status-live",
        "CACHE": "status-cache",
        "DEMO": "status-demo",
    }.get(data_status, "")
    items = [
        ("数据源", DATA_SOURCE),
        ("数据状态", data_status),
        (latest_label, latest_time or "--:--:--"),
        ("市场状态", market_text),
        ("主题口径", theme_text or "--"),
        ("CSV 快照 / 时间点", f"{snapshot_count} 行 / {captured_time_count} 个时间点"),
        ("展示模式", display_mode),
        ("板块类型", sector_type),
        ("状态说明", status_note),
    ]
    cells = []
    for label, value in items:
        value_html = (
            f"<span class='{status_class}'>{escape(str(value))}</span>"
            if label == "数据状态"
            else escape(str(value))
        )
        cells.append(
            "<div class='trust-item'>"
            f"<div class='trust-label'>{escape(label)}</div>"
            f"<div class='trust-value'>{value_html}</div>"
            "</div>"
        )
    html = (
        "<div class='trust-panel'>"
        f"<div class='trust-grid'>{''.join(cells)}</div>"
        "<div class='trust-copy'>"
        "<b>LIVE</b>：本轮页面刷新成功抓取 AKShare 数据，并使用本轮快照。<br>"
        "<b>CACHE</b>：本轮抓取失败或处于非交易时段，当前展示最近一次真实 CSV 缓存。<br>"
        "<b>DEMO</b>：模拟数据仅用于 UI 调试，不代表真实行情；DEMO 不会写入真实 CSV。"
        "</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_app_footer() -> None:
    st.markdown(
        f"<div class='footer-note'>{escape(APP_CN_NAME)} · {escape(APP_VERSION)} · Streamlit MVP<br>"
        "数据仅用于学习研究和可视化展示，不构成投资建议。</div>",
        unsafe_allow_html=True,
    )
