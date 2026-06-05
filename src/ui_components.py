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
        .status-sample { color: #f0c65a; font-weight: 850; }
        .status-history { color: #c084fc; font-weight: 850; }
        .status-empty { color: #9ca3af; font-weight: 850; }
        .small-note { color: #9ca3af; font-size: 13px; margin: 0.15rem 0 0.4rem; text-align: center; }
        .demo-alert { border: 1px solid rgba(255, 179, 0, .55); background: rgba(255, 179, 0, .10); color: #ffd166; padding: 8px 12px; border-radius: 8px; margin: 4px 0 8px; text-align: center; font-weight: 800; letter-spacing: .02em; }
        .sample-alert { border: 1px solid rgba(240, 198, 90, .42); background: rgba(240, 198, 90, .10); color: #f0c65a; padding: 8px 12px; border-radius: 8px; margin: 4px 0 8px; text-align: center; font-weight: 800; letter-spacing: .02em; }
        .cache-alert { border: 1px solid rgba(96, 165, 250, .25); background: rgba(37, 99, 235, .08); color: #bfdbfe; padding: 8px 12px; border-radius: 8px; margin: 4px 0 8px; font-size: 13px; }
        .status-badge { display: inline-flex; align-items: center; gap: 7px; border-radius: 999px; padding: 5px 10px; font-size: 12px; font-weight: 900; letter-spacing: .02em; border: 1px solid rgba(255,255,255,.14); }
        .badge-success { color: #26e07f; background: rgba(38,224,127,.10); border-color: rgba(38,224,127,.35); }
        .badge-info { color: #93c5fd; background: rgba(96,165,250,.10); border-color: rgba(96,165,250,.32); }
        .badge-warning { color: #f0c65a; background: rgba(240,198,90,.12); border-color: rgba(240,198,90,.38); }
        .badge-danger { color: #fecaca; background: rgba(248,113,113,.12); border-color: rgba(248,113,113,.38); }
        .badge-purple { color: #d8b4fe; background: rgba(192,132,252,.12); border-color: rgba(192,132,252,.38); }
        .badge-neutral { color: #d1d5db; background: rgba(156,163,175,.10); border-color: rgba(156,163,175,.24); }
        .portfolio-intro { border: 1px solid rgba(240,198,90,.24); background: linear-gradient(135deg, rgba(240,198,90,.10), rgba(8,8,8,.96) 48%, rgba(11,15,20,.95)); border-radius: 8px; padding: 13px 15px; margin: 6px 0 10px; }
        .portfolio-intro.compact { padding: 9px 12px; margin-bottom: 7px; }
        .portfolio-title { color: #f0c65a; font-size: 20px; font-weight: 900; margin-bottom: 3px; }
        .portfolio-intro.compact .portfolio-title { font-size: 16px; }
        .portfolio-subtitle { color: #e5e7eb; font-size: 13.5px; font-weight: 750; }
        .portfolio-value { color: #aab2c0; font-size: 13px; line-height: 1.55; margin: 7px 0; }
        .portfolio-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; color: #8b949e; font-size: 12.5px; margin-top: 7px; }
        .capability-list { color: #c9d1d9; font-size: 12.5px; line-height: 1.65; margin-top: 7px; }
        .notice-card { border: 1px solid rgba(255,255,255,.10); background: #080808; border-radius: 8px; padding: 10px 12px; margin: 8px 0; }
        .notice-title { color: #f3f4f6; font-weight: 850; font-size: 14px; margin-bottom: 4px; }
        .notice-body { color: #aab2c0; font-size: 13px; line-height: 1.6; }
        .notice-info { border-color: rgba(96,165,250,.25); background: rgba(37,99,235,.07); }
        .notice-warning { border-color: rgba(240,198,90,.30); background: rgba(240,198,90,.08); }
        .notice-danger { border-color: rgba(248,113,113,.30); background: rgba(127,29,29,.20); }
        .notice-success { border-color: rgba(38,224,127,.24); background: rgba(38,224,127,.07); }
        .walkthrough-card { background: #080808; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; padding: 11px 13px; min-height: 112px; margin-bottom: 8px; }
        .walkthrough-step { color: #f0c65a; font-size: 14px; font-weight: 850; margin-bottom: 5px; }
        .walkthrough-body { color: #aab2c0; font-size: 12.5px; line-height: 1.55; }
        .onboarding-card { border: 1px solid rgba(240,198,90,.28); background: linear-gradient(135deg, rgba(240,198,90,.10), rgba(11,15,20,.92)); color: #d1d5db; padding: 13px 15px; border-radius: 8px; margin: 8px 0 12px; }
        .onboarding-title { color: #f0c65a; font-weight: 850; font-size: 15px; margin-bottom: 6px; }
        .onboarding-list { margin: 4px 0 0 18px; padding: 0; line-height: 1.65; }
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
        .brief-section { background: #080808; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; padding: 14px 16px; margin: 10px 0; }
        .brief-title { color: #f0c65a; font-size: 18px; font-weight: 850; margin-bottom: 8px; }
        .brief-body { color: #c9d1d9; font-size: 13.5px; line-height: 1.75; }
        .brief-list { margin: 0; padding-left: 18px; }
        .brief-list li { margin: 5px 0; }
        .brief-pass { color: #26e07f; font-weight: 850; }
        .brief-warning { color: #ffd166; font-weight: 850; }
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


def render_status_badge(status_config: dict) -> None:
    tone = escape(str(status_config.get("tone", "neutral")))
    label = escape(str(status_config.get("label", "--")))
    short_label = escape(str(status_config.get("short_label", "--")))
    description = escape(str(status_config.get("description", "")))
    html = (
        f"<span class='status-badge badge-{tone}'>{short_label} ｜ {label}</span>"
        f"<span style='color:#8b949e;font-size:12.5px;margin-left:8px;'>{description}</span>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_portfolio_intro_card(intro_context: dict, compact: bool = False) -> None:
    status = intro_context.get("status_badge", {})
    tone = escape(str(status.get("tone", "neutral")))
    badge = (
        f"<span class='status-badge badge-{tone}'>"
        f"{escape(str(status.get('short_label', '--')))} ｜ {escape(str(status.get('label', '--')))}</span>"
    )
    caps = " / ".join(escape(str(item)) for item in intro_context.get("key_capabilities", []))
    notes = " ｜ ".join(escape(str(item)) for item in intro_context.get("boundary_notes", []))
    compact_class = " compact" if compact else ""
    extra = "" if compact else f"<div class='capability-list'>核心能力：{caps}</div><div class='capability-list'>边界：{notes}</div>"
    html = (
        f"<div class='portfolio-intro{compact_class}'>"
        f"<div class='portfolio-title'>{escape(str(intro_context.get('title', APP_CN_NAME)))}</div>"
        f"<div class='portfolio-subtitle'>{escape(str(intro_context.get('subtitle', '')))}</div>"
        f"<div class='portfolio-value'>{escape(str(intro_context.get('value_proposition', '')))}不构成投资建议。</div>"
        f"<div class='portfolio-meta'>{badge}<span>数据日期：{escape(str(intro_context.get('selected_date', '--')))}</span>"
        f"<span>展示模式：{escape(str(intro_context.get('mode_label', '--')))}</span>"
        f"<span>{escape(str(intro_context.get('app_version', APP_VERSION)))}</span></div>"
        f"{extra}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_compact_notice(title: str, body: str, tone: str = "info") -> None:
    tone = tone if tone in {"info", "warning", "danger", "success"} else "info"
    html = (
        f"<div class='notice-card notice-{tone}'>"
        f"<div class='notice-title'>{escape(str(title))}</div>"
        f"<div class='notice-body'>{escape(str(body))}</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_demo_walkthrough_cards(steps: list[dict]) -> None:
    if not steps:
        return
    st.markdown("<div class='radar-section-title'>作品集演示步骤</div>", unsafe_allow_html=True)
    cols = st.columns(3)
    for idx, step in enumerate(steps):
        html = (
            "<div class='walkthrough-card'>"
            f"<div class='walkthrough-step'>{idx + 1}. {escape(str(step.get('step_title', '--')))}</div>"
            f"<div class='walkthrough-body'>位置：{escape(str(step.get('target_tab', '--')))}</div>"
            f"<div class='walkthrough-body'>{escape(str(step.get('description', '')))}</div>"
            f"<div class='walkthrough-body'>看点：{escape(str(step.get('expected_user_takeaway', '')))}</div>"
            "</div>"
        )
        with cols[idx % 3]:
            st.markdown(html, unsafe_allow_html=True)


def render_screenshot_checklist(checklist: list[dict]) -> None:
    if not checklist:
        return
    st.markdown("<div class='radar-section-title'>截图准备清单</div>", unsafe_allow_html=True)
    rows = []
    for item in checklist:
        rows.append(
            [
                item.get("screenshot_name", "--"),
                item.get("target_tab", "--"),
                item.get("recommended_mode", "--"),
                item.get("recommended_data_source", "--"),
                item.get("what_to_capture", "--"),
            ]
        )
    _render_simple_table(["文件名", "目标 tab", "展示模式", "数据来源", "截图重点"], rows, "暂无截图建议。")


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
    selected_snapshot_date: str | None = None,
    captured_time_count: int | None = None,
    quality_label: str | None = None,
    data_source_label: str | None = None,
) -> None:
    market_text = STATUS_TEXT.get(market_status, market_status)
    source_text = data_source_label or DATA_SOURCE
    status_class = {
        "LIVE": "status-live",
        "CACHE": "status-cache",
        "DEMO": "status-demo",
        "SAMPLE": "status-sample",
        "HISTORY": "status-history",
        "EMPTY": "status-empty",
    }.get(data_status, "")
    snapshot_bits = ""
    if selected_snapshot_date:
        snapshot_bits += f" ｜ 数据日期：<b>{escape(str(selected_snapshot_date))}</b>"
    if captured_time_count is not None:
        snapshot_bits += f" ｜ 时间点：<b>{int(captured_time_count)}</b>"
    if quality_label:
        snapshot_bits += f" ｜ 质量：<b>{escape(str(quality_label))}</b>"
    html = (
        "<div class='compact-status'>"
        f"数据源：<b>{escape(source_text)}</b> ｜ "
        f"数据状态：<span class='{status_class}'>{escape(data_status)}</span> ｜ "
        f"状态说明：<b>{escape(status_note)}</b> ｜ "
        f"市场状态：<b>{escape(market_text)}</b> ｜ "
        f"{escape(latest_label)}：<b>{escape(latest_time or '--:--:--')}</b> ｜ "
        f"刷新：<b>{refresh_interval}秒</b> ｜ "
        f"板块类型：<b>{escape(sector_type)}</b>"
        f"{snapshot_bits}"
        f"{f' ｜ {escape(extra_text)}' if extra_text else ''}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    if data_status == "DEMO":
        st.markdown(
            "<div class='demo-alert'>DEMO MODE - 当前为模拟数据，不是真实行情</div>",
            unsafe_allow_html=True,
        )
    elif data_status == "SAMPLE":
        st.markdown(
            "<div class='sample-alert'>SAMPLE MODE - 当前为仓库内置合成样例数据，不代表真实行情</div>",
            unsafe_allow_html=True,
        )
    elif data_status == "HISTORY":
        st.markdown(
            "<div class='cache-alert'>历史回放，本页展示本地 CSV 缓存，不代表实时行情。</div>",
            unsafe_allow_html=True,
        )
    elif data_status == "EMPTY":
        st.markdown(
            "<div class='cache-alert'>暂无可用真实缓存，可等待抓取或启用 DEMO 测试 UI。</div>",
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


def render_fund_profile_csv_panel(
    csv_path: str,
    validation_report: dict,
    profile_summary_df: pd.DataFrame,
    exposure_df: pd.DataFrame,
    merged_df: pd.DataFrame,
    observation_summary_df: pd.DataFrame,
    max_rows: int = 24,
) -> None:
    st.markdown("<div class='radar-section-title'>基金/ETF 主题暴露配置</div>", unsafe_allow_html=True)
    html = (
        "<div class='trust-panel'>"
        "<div class='trust-grid'>"
        "<div class='trust-item'><div class='trust-label'>默认 JSON 配置</div><div class='trust-value'>config/fund_profiles.json</div></div>"
        f"<div class='trust-item'><div class='trust-label'>CSV 示例模板</div><div class='trust-value'>{escape(csv_path)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>校验状态</div><div class='trust-value'>{escape(str(validation_report.get('validation_label', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>Profile 数量</div><div class='trust-value'>{int(validation_report.get('profile_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>CSV 行数</div><div class='trust-value'>{int(validation_report.get('row_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>Warning / Error</div><div class='trust-value'>{int(validation_report.get('warning_count', 0) or 0)} / {int(validation_report.get('error_count', 0) or 0)}</div></div>"
        "</div>"
        "<div class='trust-copy'>CSV 只表达基金/ETF 与主题的暴露关系，不是账户持仓文件，不包含真实金额、份额、成本或收益；"
        "它不读取真实账户，不触发 AKShare，也不会写入 data/ticks。</div>"
        f"<div class='trust-copy'>{escape(str(validation_report.get('validation_reason', '')))}</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)

    warnings = list(validation_report.get("warnings") or [])
    errors = list(validation_report.get("errors") or [])
    unknown = list(validation_report.get("unknown_themes") or [])
    if warnings or errors:
        details = [f"Error: {item}" for item in errors] + [f"Warning: {item}" for item in warnings]
        st.markdown(
            "<div class='holding-warning'>"
            + "<br>".join(escape(str(item)) for item in details[:8])
            + ("<br>..." if len(details) > 8 else "")
            + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div class='concept-note'>配置校验通过。主题名称已与当前主题库对齐。</div>", unsafe_allow_html=True)
    if unknown:
        st.markdown(
            f"<div class='holding-warning'>未注册主题：{escape('，'.join(map(str, unknown)))}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div class='radar-section-title'>CSV Profile 概览</div>", unsafe_allow_html=True)
    summary_rows = []
    if profile_summary_df is not None and not profile_summary_df.empty:
        for _, row in profile_summary_df.head(max_rows).iterrows():
            summary_rows.append(
                [
                    row.get("profile_name", "--"),
                    row.get("fund_code", "--"),
                    row.get("fund_type", "--"),
                    int(row.get("theme_count", 0) or 0),
                    f"{float(row.get('total_exposure_weight', 0) or 0):.2f}",
                    int(row.get("core_theme_count", 0) or 0),
                    row.get("validation_label", "--"),
                ]
            )
    _render_simple_table(["Profile", "代码", "类型", "主题数", "权重合计", "核心主题", "校验"], summary_rows, "暂无 CSV profile 概览。")

    with st.expander("CSV 主题暴露明细", expanded=False):
        exposure_rows = []
        if exposure_df is not None and not exposure_df.empty:
            for _, row in exposure_df.head(max_rows).iterrows():
                exposure_rows.append(
                    [
                        row.get("profile_name", "--"),
                        row.get("theme_name", "--"),
                        row.get("theme_group", "--"),
                        f"{float(row.get('exposure_weight', 0) or 0):.1%}",
                        row.get("exposure_role", "--"),
                        "是" if bool(row.get("taxonomy_registered")) else "否",
                    ]
                )
        _render_simple_table(["Profile", "主题", "分组", "权重", "角色", "已注册"], exposure_rows, "暂无 CSV 主题暴露明细。")

    st.markdown("<div class='radar-section-title'>CSV 持仓相关观察摘要</div>", unsafe_allow_html=True)
    observation_rows = []
    if observation_summary_df is not None and not observation_summary_df.empty:
        for _, row in observation_summary_df.head(max_rows).iterrows():
            observation_rows.append(
                [
                    row.get("profile_name", "--"),
                    row.get("fund_code", "--"),
                    int(row.get("related_theme_count", 0) or 0),
                    int(row.get("positive_theme_count", 0) or 0),
                    int(row.get("pressure_theme_count", 0) or 0),
                    int(row.get("unknown_theme_count", 0) or 0),
                    f"{float(row.get('weighted_net_inflow_score', 0) or 0):.2f}",
                    row.get("profile_observation_label", "--"),
                ]
            )
    _render_simple_table(["Profile", "代码", "主题数", "偏强", "承压", "未注册", "观察分", "状态"], observation_rows, "暂无 CSV 观察摘要。")

    with st.expander("CSV 主题雷达合并明细", expanded=False):
        merged_rows = []
        if merged_df is not None and not merged_df.empty:
            for _, row in merged_df.head(max_rows).iterrows():
                amount = pd.to_numeric(pd.Series([row.get("main_net_inflow_billion")]), errors="coerce").iloc[0]
                merged_rows.append(
                    [
                        row.get("profile_name", "--"),
                        row.get("theme_name", "--"),
                        f"{float(row.get('exposure_weight', 0) or 0):.1%}",
                        row.get("theme_status") or "样本不足",
                        "--" if pd.isna(amount) else format_billion(amount),
                        row.get("observation_label", "--"),
                        row.get("observation_reason", "--"),
                    ]
                )
        _render_simple_table(["Profile", "主题", "权重", "主题状态", "主力净流入", "观察", "说明"], merged_rows, "暂无 CSV 合并观察明细。")


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


def render_multi_day_trend_overview(summary: dict, date_count: int) -> None:
    html = (
        "<div class='radar-section-title'>多日趋势概览</div>"
        "<div class='hotspot-overview'>"
        "<div class='hotspot-card'>"
        "<div class='holding-label'>多日主题状态</div>"
        f"<div class='hotspot-value'>{escape(str(summary.get('summary_label', '--')))}</div>"
        f"<div class='hotspot-body'>{escape(str(summary.get('summary_reason', '')))}</div>"
        "</div>"
        f"<div class='hotspot-card'><div class='holding-label'>可用缓存日期</div><div class='hotspot-value'>{int(date_count or 0)}</div></div>"
        f"<div class='hotspot-card'><div class='holding-label'>参与分析日期</div><div class='hotspot-value'>{int(summary.get('date_count', 0) or 0)}</div></div>"
        f"<div class='hotspot-card'><div class='holding-label'>覆盖主题数</div><div class='hotspot-value'>{int(summary.get('total_themes', 0) or 0)}</div></div>"
        f"<div class='hotspot-card'><div class='holding-label'>偏强 / 改善 / 承压 / 分化</div><div class='hotspot-value'>{int(summary.get('strength_count', 0) or 0)} / {int(summary.get('improving_count', 0) or 0)} / {int(summary.get('pressure_count', 0) or 0)} / {int(summary.get('mixed_count', 0) or 0)}</div></div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_multi_day_trend_cards(title: str, trend_df: pd.DataFrame, max_cards: int = 6) -> None:
    st.markdown(f"<div class='radar-section-title'>{escape(title)}</div>", unsafe_allow_html=True)
    if trend_df is None or trend_df.empty:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>当前暂无该类多日趋势。</div></div>", unsafe_allow_html=True)
        return
    cols = st.columns(3)
    for idx, row in enumerate(trend_df.head(max_cards).to_dict("records")):
        latest_value = float(row.get("latest_value", 0) or 0)
        amount_class = "amount-in" if latest_value >= 0 else "amount-out"
        html = (
            "<div class='hotspot-card'>"
            f"<div class='hotspot-title'>{escape(str(row.get('theme_name', '--')))}</div>"
            f"<div class='hotspot-label'>{escape(str(row.get('trend_label', '--')))}</div>"
            f"<div class='hotspot-value {amount_class}'>{escape(format_billion(row.get('latest_value')))}</div>"
            f"<div class='hotspot-body'>变化：{escape(format_billion(row.get('value_change')))} ｜ 日期：{escape(str(row.get('first_date', '--')))} → {escape(str(row.get('latest_date', '--')))}</div>"
            f"<div class='hotspot-body'>流入占比：{float(row.get('positive_ratio', 0) or 0):.0%} ｜ 流出占比：{float(row.get('negative_ratio', 0) or 0):.0%}</div>"
            f"<div class='hotspot-body'>状态：{escape(str(row.get('latest_status', '--')))} ｜ 来源数：{int(row.get('latest_source_count', 0) or 0)}</div>"
            f"<div class='hotspot-body'>来源：{escape(_shorten_sectors(row.get('latest_source_sectors'), max_items=4))}</div>"
            f"<div class='hotspot-body'>{escape(str(row.get('trend_reason', '')))}</div>"
            "</div>"
        )
        with cols[idx % 3]:
            st.markdown(html, unsafe_allow_html=True)


def render_multi_day_trend_table(trend_pool_df: pd.DataFrame, max_rows: int = 30) -> None:
    st.markdown("<div class='radar-section-title'>多日趋势明细</div>", unsafe_allow_html=True)
    if trend_pool_df is None or trend_pool_df.empty:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>暂无多日趋势明细。</div></div>", unsafe_allow_html=True)
        return
    headers = ["主题", "趋势标签", "最早金额", "最新金额", "多日变化", "流入占比", "流出占比", "最新状态", "说明"]
    rows = []
    for _, row in trend_pool_df.head(max_rows).iterrows():
        latest = float(row.get("latest_value", 0) or 0)
        amount_class = "amount-in" if latest >= 0 else "amount-out"
        values = [
            row.get("theme_name", "--"),
            row.get("trend_label", "--"),
            format_billion(row.get("first_value")),
            format_billion(row.get("latest_value")),
            format_billion(row.get("value_change")),
            f"{float(row.get('positive_ratio', 0) or 0):.0%}",
            f"{float(row.get('negative_ratio', 0) or 0):.0%}",
            row.get("latest_status", "--"),
            row.get("trend_reason", "--"),
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


def render_first_run_guide(reason: str | None = None) -> None:
    detail = escape(reason or "当前没有可用真实缓存或实时抓取暂不可用。")
    html = (
        "<div class='onboarding-card'>"
        "<div class='onboarding-title'>首次访问提示</div>"
        f"<div>{detail} 你可以：</div>"
        "<ol class='onboarding-list'>"
        "<li>切换到 <b>SAMPLE 演示样例数据</b>，完整体验页面功能。</li>"
        "<li>开启 <b>DEMO</b> 测试 UI。</li>"
        "<li>稍后重试真实数据抓取。</li>"
        "</ol>"
        "<div class='radar-meta'>SAMPLE 是仓库内置合成 CSV，不代表真实行情，不触发 AKShare，也不会写入 data/ticks。</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


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
    selected_snapshot_date: str | None = None,
    quality_label: str | None = None,
    data_source_label: str | None = None,
) -> None:
    market_text = STATUS_TEXT.get(market_status, market_status)
    theme_text = theme_mode_label if display_mode == "基金观察池" else "原始板块"
    source_text = data_source_label or DATA_SOURCE
    status_class = {
        "LIVE": "status-live",
        "CACHE": "status-cache",
        "DEMO": "status-demo",
        "SAMPLE": "status-sample",
        "HISTORY": "status-history",
        "EMPTY": "status-empty",
    }.get(data_status, "")
    items = [
        ("数据源", source_text),
        ("数据状态", data_status),
        ("数据日期", selected_snapshot_date or "--"),
        (latest_label, latest_time or "--:--:--"),
        ("市场状态", market_text),
        ("主题口径", theme_text or "--"),
        ("CSV 快照 / 时间点", f"{snapshot_count} 行 / {captured_time_count} 个时间点"),
        ("快照质量", quality_label or "--"),
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
        "<b>HISTORY</b>：历史回放，只读取所选日期的本地 CSV，不触发 AKShare 抓取，也不会写入 CSV。<br>"
        "<b>DEMO</b>：模拟数据仅用于 UI 调试，不代表真实行情；DEMO 不会写入真实 CSV。<br>"
        "<b>SAMPLE</b>：仓库内置合成 CSV 示例数据，只读展示，不代表真实行情，也不会写入真实缓存。<br>"
        "<b>EMPTY</b>：暂无可用真实缓存，可等待抓取或启用 DEMO 测试 UI。"
        "</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_snapshot_quality_cards(report: dict) -> None:
    st.markdown("<div class='radar-section-title'>CSV 快照数据质量</div>", unsafe_allow_html=True)
    html = (
        "<div class='trust-panel'>"
        "<div class='trust-grid'>"
        f"<div class='trust-item'><div class='trust-label'>本地真实缓存</div><div class='trust-value'>{int(report.get('local_file_count', 0) or 0)} 个文件</div></div>"
        f"<div class='trust-item'><div class='trust-label'>本地缓存行数</div><div class='trust-value'>{int(report.get('local_total_rows', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>本地最新日期</div><div class='trust-value'>{escape(str(report.get('local_latest_date') or '--'))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>本地质量</div><div class='trust-value'>{escape(str(report.get('local_quality_label', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>本地 Warning / Error</div><div class='trust-value'>{int(report.get('local_warning_count', 0) or 0)} / {int(report.get('local_error_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>SAMPLE 文件</div><div class='trust-value'>{int(report.get('sample_file_count', 0) or 0)} 个文件</div></div>"
        f"<div class='trust-item'><div class='trust-label'>SAMPLE 行数</div><div class='trust-value'>{int(report.get('sample_total_rows', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>SAMPLE 最新日期</div><div class='trust-value'>{escape(str(report.get('sample_latest_date') or '--'))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>SAMPLE 质量</div><div class='trust-value'>{escape(str(report.get('sample_quality_label', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>SAMPLE Warning / Error</div><div class='trust-value'>{int(report.get('sample_warning_count', 0) or 0)} / {int(report.get('sample_error_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>治理状态</div><div class='trust-value'>{escape(str(report.get('report_label', '--')))}</div></div>"
        "</div>"
        f"<div class='trust-copy'>{escape(str(report.get('report_reason', '')))}</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_snapshot_quality_notes(report: dict) -> None:
    warnings = []
    errors = []
    for label, catalog in (
        ("本地真实缓存", report.get("local_catalog_df")),
        ("SAMPLE 样例数据", report.get("sample_catalog_df")),
    ):
        if isinstance(catalog, pd.DataFrame) and not catalog.empty:
            issue_rows = catalog[(catalog.get("warning_count", 0) > 0) | (catalog.get("error_count", 0) > 0)]
            for _, row in issue_rows.iterrows():
                text = (
                    f"{label} {row.get('file_name', '--')}："
                    f"warning={int(row.get('warning_count', 0) or 0)}, "
                    f"error={int(row.get('error_count', 0) or 0)}, "
                    f"quality={row.get('quality_label', '--')}"
                )
                if int(row.get("error_count", 0) or 0):
                    errors.append(text)
                else:
                    warnings.append(text)
    if not warnings and not errors:
        st.markdown(
            "<div class='concept-note'>当前 CSV 快照质量检查未发现明显 warning/error。数据质量检查只做文件和字段检查，不做投资判断。</div>",
            unsafe_allow_html=True,
        )
        return
    with st.expander("查看 CSV 快照 warning / error", expanded=False):
        if errors:
            st.markdown("<div class='holding-warning'>" + "<br>".join(escape(item) for item in errors[:12]) + "</div>", unsafe_allow_html=True)
        if warnings:
            st.markdown("<div class='concept-note'>" + "<br>".join(escape(item) for item in warnings[:12]) + "</div>", unsafe_allow_html=True)


def render_snapshot_catalog_table(catalog_df: pd.DataFrame, title: str = "CSV 快照目录", max_rows: int = 30) -> None:
    st.markdown(f"<div class='radar-section-title'>{escape(title)}</div>", unsafe_allow_html=True)
    if catalog_df is None or catalog_df.empty:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>暂无本地 CSV 快照。</div></div>", unsafe_allow_html=True)
        return
    is_quality_catalog = "file_name" in catalog_df.columns
    headers = (
        ["文件", "日期", "行数", "时间点", "最新时间", "文件大小", "质量标签", "Warning", "Error"]
        if is_quality_catalog
        else ["日期", "行数", "时间点", "最新时间", "行业行数", "概念行数", "文件大小", "质量标签", "说明"]
    )
    rows = []
    for _, row in catalog_df.head(max_rows).iterrows():
        if is_quality_catalog:
            values = [
                row.get("file_name", "--"),
                row.get("data_date", "--"),
                int(row.get("row_count", 0) or 0),
                int(row.get("captured_time_count", 0) or 0),
                row.get("latest_captured_time") or "--",
                f"{float(row.get('file_size_kb', 0) or 0):.1f} KB",
                row.get("quality_label", "--"),
                int(row.get("warning_count", 0) or 0),
                int(row.get("error_count", 0) or 0),
            ]
        else:
            values = [
                row.get("snapshot_date", "--"),
                int(row.get("row_count", 0) or 0),
                int(row.get("captured_time_count", 0) or 0),
                row.get("latest_captured_time") or "--",
                int(row.get("industry_rows", 0) or 0),
                int(row.get("concept_rows", 0) or 0),
                f"{float(row.get('file_size_kb', 0) or 0):.1f} KB",
                row.get("quality_label", "--"),
                row.get("quality_reason", "--"),
            ]
        cells = "".join(f"<td>{escape(str(value))}</td>" for value in values)
        rows.append(f"<tr>{cells}</tr>")
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


def render_warehouse_status_cards(summary: dict, audit: dict | None = None) -> None:
    audit = audit or {}
    st.markdown("<div class='radar-section-title'>本地 SQLite Warehouse（可重建索引）</div>", unsafe_allow_html=True)
    html = (
        "<div class='trust-panel'>"
        "<div class='trust-grid'>"
        f"<div class='trust-item'><div class='trust-label'>Warehouse 状态</div><div class='trust-value'>{escape(str(summary.get('warehouse_label', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>文件记录</div><div class='trust-value'>{int(summary.get('snapshot_file_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>索引行数</div><div class='trust-value'>{int(summary.get('snapshot_row_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>LOCAL 文件 / 行</div><div class='trust-value'>{int(summary.get('local_file_count', 0) or 0)} / {int(summary.get('local_row_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>SAMPLE 文件 / 行</div><div class='trust-value'>{int(summary.get('sample_file_count', 0) or 0)} / {int(summary.get('sample_row_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>最新 LOCAL 日期</div><div class='trust-value'>{escape(str(summary.get('latest_local_date') or '--'))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>最新 SAMPLE 日期</div><div class='trust-value'>{escape(str(summary.get('latest_sample_date') or '--'))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>Audit</div><div class='trust-value'>{escape(str(audit.get('audit_label', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>Warning / Error</div><div class='trust-value'>{int(audit.get('warning_count', 0) or 0)} / {int(audit.get('error_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>重复 / 空名称</div><div class='trust-value'>{int(audit.get('duplicate_row_count', 0) or 0)} / {int(audit.get('empty_sector_name_count', 0) or 0)}</div></div>"
        "</div>"
        f"<div class='trust-copy'>{escape(str(summary.get('warehouse_reason', '')))}</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_warehouse_date_table(dates_df: pd.DataFrame, max_rows: int = 30) -> None:
    st.markdown("<div class='radar-section-title'>Warehouse 可用日期</div>", unsafe_allow_html=True)
    if dates_df is None or dates_df.empty:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>暂无 SQLite warehouse 日期索引。</div></div>", unsafe_allow_html=True)
        return
    headers = ["来源", "日期", "行数", "时间点", "最新时间"]
    rows = []
    for _, row in dates_df.head(max_rows).iterrows():
        rows.append(
            [
                row.get("source_type", "--"),
                row.get("data_date", "--"),
                int(row.get("row_count", 0) or 0),
                int(row.get("captured_time_count", 0) or 0),
                row.get("latest_captured_time") or "--",
            ]
        )
    _render_simple_table(headers, rows, "暂无 SQLite warehouse 日期索引。")


def render_warehouse_notes(summary: dict, audit: dict | None = None) -> None:
    audit = audit or {}
    st.markdown(
        "<div class='concept-note'>CSV 仍是主数据来源；SQLite warehouse 只是本地可重建查询索引。"
        "没有 warehouse 时 app 仍然按 CSV 路径运行。页面只读取 warehouse 状态，不会自动重建，也不会写入 SQLite。</div>",
        unsafe_allow_html=True,
    )
    warnings = list(audit.get("warnings") or [])
    errors = list(audit.get("errors") or [])
    if not warnings and not errors:
        return
    with st.expander("查看 warehouse warning / error", expanded=False):
        if errors:
            st.markdown("<div class='holding-warning'>" + "<br>".join(escape(str(item)) for item in errors[:12]) + "</div>", unsafe_allow_html=True)
        if warnings:
            st.markdown("<div class='concept-note'>" + "<br>".join(escape(str(item)) for item in warnings[:12]) + "</div>", unsafe_allow_html=True)


def _render_simple_table(headers: list[str], rows: list[list[object]], empty_message: str) -> None:
    if not rows:
        st.markdown(f"<div class='rank-panel'><div class='rank-empty'>{escape(empty_message)}</div></div>", unsafe_allow_html=True)
        return
    head = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
    body_rows = []
    for row in rows:
        body_rows.append("<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>")
    html = (
        "<div class='rank-panel'>"
        "<table class='rank-table'>"
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_theme_taxonomy_status(taxonomy: dict, warnings: list[str], coverage_report: dict, consistency: dict) -> None:
    name = taxonomy.get("taxonomy_name", "主题库") if isinstance(taxonomy, dict) else "主题库"
    version = taxonomy.get("version", "--") if isinstance(taxonomy, dict) else "--"
    coverage_label = coverage_report.get("coverage_label", "--") if isinstance(coverage_report, dict) else "--"
    consistency_label = consistency.get("consistency_label", "--") if isinstance(consistency, dict) else "--"
    warning_text = f" ｜ warning {len(warnings)}" if warnings else ""
    st.markdown(
        "<div class='concept-note'>"
        f"当前主题库：<b>{escape(str(name))} {escape(str(version))}</b> ｜ "
        f"覆盖状态：<b>{escape(str(coverage_label))}</b> ｜ "
        f"主题一致性：<b>{escape(str(consistency_label))}</b>{escape(warning_text)}。"
        "主题库是轻量规则，用于基金主题观察，不等同于正式行业分类。严格代表口径更克制，广度观察可能包含上下级重复。"
        "</div>",
        unsafe_allow_html=True,
    )


def render_theme_taxonomy_panel(
    taxonomy: dict,
    warnings: list[str],
    consistency: dict,
    definition_df: pd.DataFrame,
) -> None:
    st.markdown("#### 主题库说明")
    name = taxonomy.get("taxonomy_name", "--") if isinstance(taxonomy, dict) else "--"
    version = taxonomy.get("version", "--") if isinstance(taxonomy, dict) else "--"
    description = taxonomy.get("description", "") if isinstance(taxonomy, dict) else ""
    html = (
        "<div class='trust-panel'>"
        "<div class='trust-grid'>"
        f"<div class='trust-item'><div class='trust-label'>主题库</div><div class='trust-value'>{escape(str(name))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>版本</div><div class='trust-value'>{escape(str(version))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>主题数量</div><div class='trust-value'>{int(consistency.get('taxonomy_theme_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>配置提示</div><div class='trust-value'>{len(warnings)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>一致性</div><div class='trust-value'>{escape(str(consistency.get('consistency_label', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>说明</div><div class='trust-value'>{escape(str(description)[:80])}</div></div>"
        "</div>"
        f"<div class='trust-copy'>{escape(str(consistency.get('consistency_reason', '')))}<br>"
        "主题库是轻量规则，用于基金主题观察，不等同于正式行业分类，不构成投资建议。</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    if warnings:
        st.markdown(
            "<div class='holding-warning'>" + "<br>".join(escape(str(item)) for item in warnings[:8]) + "</div>",
            unsafe_allow_html=True,
        )
    if consistency.get("watchlist_missing_in_taxonomy") or consistency.get("fund_profile_missing_in_taxonomy"):
        st.markdown(
            "<div class='holding-warning'>"
            f"watchlist 未注册：{escape('，'.join(consistency.get('watchlist_missing_in_taxonomy') or []) or '无')}<br>"
            f"fund_profiles 未注册：{escape('，'.join(consistency.get('fund_profile_missing_in_taxonomy') or []) or '无')}"
            "</div>",
            unsafe_allow_html=True,
        )
    st.markdown("<div class='radar-section-title'>主题定义表</div>", unsafe_allow_html=True)
    rows = []
    if definition_df is not None and not definition_df.empty:
        for _, row in definition_df.head(12).iterrows():
            rows.append(
                [
                    row.get("theme_name", "--"),
                    row.get("theme_group", "--"),
                    _shorten_sectors(row.get("primary_sectors"), max_items=4),
                    _shorten_sectors(row.get("related_sectors"), max_items=5),
                    _shorten_sectors(row.get("concept_keywords"), max_items=5),
                    row.get("overlap_notes", "--"),
                ]
            )
    _render_simple_table(["主题", "分组", "核心行业", "相关行业", "概念关键词", "重叠说明"], rows, "暂无主题定义。")


def render_theme_coverage_panel(
    coverage_report: dict,
    usage_df: pd.DataFrame,
    overlap_df: pd.DataFrame,
) -> None:
    st.markdown("#### 主题覆盖审计")
    if not coverage_report:
        st.markdown("<div class='rank-panel'><div class='rank-empty'>暂无可审计快照。</div></div>", unsafe_allow_html=True)
        return
    ratio = float(coverage_report.get("coverage_ratio", 0) or 0)
    html = (
        "<div class='trust-panel'>"
        "<div class='trust-grid'>"
        f"<div class='trust-item'><div class='trust-label'>覆盖状态</div><div class='trust-value'>{escape(str(coverage_report.get('coverage_label', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>覆盖率</div><div class='trust-value'>{ratio:.1%}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>总板块</div><div class='trust-value'>{int(coverage_report.get('total_sectors', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>已覆盖</div><div class='trust-value'>{int(coverage_report.get('covered_sector_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>未覆盖</div><div class='trust-value'>{int(coverage_report.get('uncovered_sector_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>高资金未覆盖</div><div class='trust-value'>{len(coverage_report.get('high_flow_uncovered_df', pd.DataFrame()))}</div></div>"
        "</div>"
        f"<div class='trust-copy'>{escape(str(coverage_report.get('coverage_reason', '')))}</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)

    high_flow = coverage_report.get("high_flow_uncovered_df", pd.DataFrame())
    rows = []
    if isinstance(high_flow, pd.DataFrame) and not high_flow.empty:
        for _, row in high_flow.head(12).iterrows():
            rows.append([row.get("sector_name", "--"), format_billion(row.get("main_net_inflow_billion")), format_billion(row.get("abs_main_net_inflow_billion"))])
    st.markdown("<div class='radar-section-title'>高资金流未覆盖板块</div>", unsafe_allow_html=True)
    _render_simple_table(["板块", "主力净流入", "绝对金额"], rows, "暂无高资金流未覆盖板块。")

    overlap_rows = []
    if overlap_df is not None and not overlap_df.empty:
        for _, row in overlap_df.head(12).iterrows():
            overlap_rows.append([row.get("sector_name", "--"), row.get("theme_names", "--"), row.get("overlap_type", "--"), row.get("warning_reason", "--")])
    st.markdown("<div class='radar-section-title'>重复映射 Warning</div>", unsafe_allow_html=True)
    _render_simple_table(["板块", "主题", "类型", "说明"], overlap_rows, "暂无重复映射 warning。")

    usage_rows = []
    if usage_df is not None and not usage_df.empty:
        for _, row in usage_df.head(12).iterrows():
            usage_rows.append(
                [
                    row.get("theme_name", "--"),
                    row.get("theme_group", "--"),
                    format_billion(row.get("main_net_inflow_billion")),
                    row.get("theme_status", "--"),
                    row.get("match_strategy", "--"),
                    int(row.get("source_count", 0) or 0),
                    row.get("coverage_note", "--"),
                ]
            )
    st.markdown("<div class='radar-section-title'>主题使用情况</div>", unsafe_allow_html=True)
    _render_simple_table(["主题", "分组", "主力净流入", "状态", "匹配策略", "来源数", "说明"], usage_rows, "暂无主题使用情况。")


def _render_brief_list(items: list[str], empty_message: str = "暂无内容。") -> str:
    values = [escape(str(item)) for item in (items or []) if str(item).strip()]
    if not values:
        values = [escape(empty_message)]
    return "<ul class='brief-list'>" + "".join(f"<li>{item}</li>" for item in values) + "</ul>"


def render_brief_overview_cards(
    data_context: dict,
    brief: dict,
    forbidden_hits: list[str],
) -> None:
    status_text = "通过" if not forbidden_hits else "需检查"
    status_class = "brief-pass" if not forbidden_hits else "brief-warning"
    html = (
        "<div class='trust-panel'>"
        "<div class='trust-grid'>"
        f"<div class='trust-item'><div class='trust-label'>数据日期</div><div class='trust-value'>{escape(str(data_context.get('selected_date', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>视图状态</div><div class='trust-value'>{escape(str(data_context.get('view_status', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>主题口径</div><div class='trust-value'>{escape(str(data_context.get('theme_mode_label', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>时间点数量</div><div class='trust-value'>{int(data_context.get('captured_time_count', 0) or 0)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>简报状态</div><div class='trust-value'>{escape(str(brief.get('brief_title', '观察简报')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>禁词检查</div><div class='trust-value {status_class}'>{status_text}</div></div>"
        "</div>"
        f"<div class='trust-copy'>{escape(str(data_context.get('data_context_reason', '')))}</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    if forbidden_hits:
        st.markdown(
            "<div class='holding-warning'>简报命中动作性表达，已暂不提供下载："
            f"{escape('，'.join(forbidden_hits))}</div>",
            unsafe_allow_html=True,
        )


def render_observation_brief_cards(brief: dict) -> None:
    st.markdown(
        "<div class='brief-section'>"
        "<div class='brief-title'>摘要</div>"
        f"<div class='brief-body'>{escape(str(brief.get('executive_summary') or '暂无可用摘要。'))}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    sections = [
        ("关键观察", brief.get("key_points") or []),
        ("口径风险", brief.get("risk_notes") or []),
        ("数据说明", brief.get("data_notes") or []),
    ]
    for title, items in sections:
        st.markdown(
            "<div class='brief-section'>"
            f"<div class='brief-title'>{escape(title)}</div>"
            f"<div class='brief-body'>{_render_brief_list(items)}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<div class='brief-section'>"
        "<div class='brief-title'>免责声明</div>"
        f"<div class='brief-body'>{escape(str(brief.get('disclaimer') or ''))}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_brief_download(
    markdown_text: str,
    selected_date: str,
    forbidden_hits: list[str] | None = None,
    file_name: str | None = None,
    label: str = "下载 Markdown 简报",
) -> None:
    if forbidden_hits:
        st.markdown(
            "<div class='holding-warning'>禁词检查未通过，已关闭 Markdown 下载。</div>",
            unsafe_allow_html=True,
        )
        return
    safe_date = "".join(ch for ch in str(selected_date or "unknown") if ch.isdigit() or ch == "-") or "unknown"
    st.download_button(
        label,
        data=markdown_text,
        file_name=file_name or f"yangjibao_brief_{safe_date}.md",
        mime="text/markdown",
        type="secondary",
    )


def render_brief_template_meta_cards(metadata: dict, compliance: dict, template_mode: str) -> None:
    forbidden_hits = compliance.get("forbidden_hits") or []
    status_class = "brief-pass" if not forbidden_hits and compliance.get("compliance_label") == "合规通过" else "brief-warning"
    real_label = "真实行情/缓存" if metadata.get("is_real_market_data") else "非真实行情数据"
    html = (
        "<div class='trust-panel'>"
        "<div class='trust-grid'>"
        f"<div class='trust-item'><div class='trust-label'>简报模板</div><div class='trust-value'>{escape(str(template_mode))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>生成时间</div><div class='trust-value'>{escape(str(metadata.get('generated_at', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>数据状态</div><div class='trust-value'>{escape(str(metadata.get('view_status', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>数据性质</div><div class='trust-value'>{escape(real_label)}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>合规状态</div><div class='trust-value {status_class}'>{escape(str(compliance.get('compliance_label', '--')))}</div></div>"
        f"<div class='trust-item'><div class='trust-label'>章节数量</div><div class='trust-value'>{int(compliance.get('section_count', 0) or 0)}</div></div>"
        "</div>"
        f"<div class='trust-copy'>{escape(str(metadata.get('data_notice', '')))}</div>"
        f"<div class='trust-copy'>{escape(str(compliance.get('compliance_reason', '')))}</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    if forbidden_hits:
        st.markdown(
            "<div class='holding-warning'>新版简报命中动作性表达，已暂不提供下载："
            f"{escape('，'.join(forbidden_hits))}</div>",
            unsafe_allow_html=True,
        )


def render_app_footer() -> None:
    st.markdown(
        f"<div class='footer-note'>{escape(APP_CN_NAME)} · {escape(APP_VERSION)} · Streamlit MVP<br>"
        "数据仅用于学习研究和可视化展示，不构成投资建议。</div>",
        unsafe_allow_html=True,
    )
