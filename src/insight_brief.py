from __future__ import annotations

import re
from typing import Any

import pandas as pd


FORBIDDEN_BRIEF_PATTERNS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "抄底",
    "逃顶",
    "推荐",
    "推荐买",
    "建议买",
    "建议卖",
    "建议加仓",
    "建仓",
    "清仓",
    "未来会涨",
    "未来会跌",
    "适合配置",
    "应该调仓",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _names_from_df(df: pd.DataFrame | None, name_col: str, value_col: str | None = None, top_n: int = 3) -> list[str]:
    if df is None or df.empty or name_col not in df.columns:
        return []
    work = df.copy()
    if value_col and value_col in work.columns:
        work[value_col] = pd.to_numeric(work[value_col], errors="coerce")
        work = work.sort_values(value_col, ascending=False)
    return work[name_col].dropna().astype(str).head(top_n).tolist()


def _join_names(names: list[str], empty: str = "暂无明显主题") -> str:
    return "，".join(names) if names else empty


def _status_counts(df: pd.DataFrame, status_col: str = "theme_status") -> tuple[int, int, int]:
    if df is None or df.empty or status_col not in df.columns:
        return 0, 0, 0
    statuses = df[status_col].fillna("分歧/中性").astype(str)
    positive = int(statuses.isin(["强流入", "弱流入"]).sum())
    negative = int(statuses.isin(["强流出", "弱流出"]).sum())
    neutral = int(statuses.eq("分歧/中性").sum())
    return positive, negative, neutral


def build_data_context_summary(
    selected_date: str,
    view_status: str,
    snapshot_summary: dict,
    theme_mode_label: str,
    market_status: str | None = None,
) -> dict:
    status = str(view_status or "EMPTY").upper()
    labels = {
        "LIVE": "实时观察",
        "CACHE": "缓存观察",
        "HISTORY": "历史回放",
        "DEMO": "模拟演示",
        "SAMPLE": "演示样例",
        "EMPTY": "暂无真实数据",
    }
    reasons = {
        "LIVE": "当前展示本轮成功抓取的数据，适合观察当前资金流状态。",
        "CACHE": "当前展示本地缓存数据，适合观察已保存的资金流状态。",
        "HISTORY": "当前为历史回放模式，不代表实时行情。",
        "DEMO": "当前为模拟演示数据，仅用于 UI 调试。",
        "SAMPLE": "当前展示仓库内置合成样例数据，仅用于演示页面功能，不代表真实行情。",
        "EMPTY": "当前暂无可用真实缓存，可等待抓取或使用 DEMO 测试 UI。",
    }
    return {
        "selected_date": selected_date or "--",
        "view_status": status,
        "captured_time_count": _safe_int(snapshot_summary.get("captured_time_count") if snapshot_summary else 0),
        "latest_captured_time": (snapshot_summary or {}).get("latest_captured_time") or "--:--:--",
        "theme_mode_label": theme_mode_label or "原始板块",
        "market_status": market_status or "--",
        "data_context_label": labels.get(status, "缓存观察"),
        "data_context_reason": reasons.get(status, "当前展示本地数据，适合观察已保存的资金流状态。"),
    }


def summarize_theme_radar_for_brief(
    radar_df: pd.DataFrame,
    top_n: int = 3,
) -> dict:
    if radar_df is None or radar_df.empty:
        return {
            "strongest_themes": [],
            "weakest_themes": [],
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "radar_summary_label": "主题资金分化",
            "radar_summary_reason": "当前暂无可用主题雷达快照，等待更多资金流数据。",
        }
    df = radar_df.copy()
    name_col = "theme_name" if "theme_name" in df.columns else "sector_name"
    if "main_net_inflow_billion" in df.columns:
        df["main_net_inflow_billion"] = pd.to_numeric(df["main_net_inflow_billion"], errors="coerce")
    positive_count, negative_count, neutral_count = _status_counts(df)
    if positive_count >= negative_count + 2:
        label = "主题资金偏强"
        reason = "当前流入主题数量明显多于流出主题，主题资金表现偏活跃。"
    elif negative_count >= positive_count + 2:
        label = "主题资金偏冷"
        reason = "当前流出主题数量明显多于流入主题，主题资金表现偏谨慎。"
    else:
        label = "主题资金分化"
        reason = "当前流入和流出主题并存，主题结构分化较明显。"
    strongest = df.sort_values("main_net_inflow_billion", ascending=False)[name_col].dropna().astype(str).head(top_n).tolist()
    weakest = df.sort_values("main_net_inflow_billion", ascending=True)[name_col].dropna().astype(str).head(top_n).tolist()
    return {
        "strongest_themes": strongest,
        "weakest_themes": weakest,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "radar_summary_label": label,
        "radar_summary_reason": reason,
    }


def summarize_intraday_for_brief(
    hotspot_summary: dict | None,
    hotspot_pool_df: pd.DataFrame | None,
) -> dict:
    if hotspot_pool_df is None or hotspot_pool_df.empty:
        return {
            "intraday_available": False,
            "intraday_summary_label": "日内样本不足",
            "positive_hotspots": [],
            "pressure_hotspots": [],
            "key_intraday_themes": [],
            "intraday_summary_reason": "当前快照数量不足，暂无法判断日内变化。",
        }
    df = hotspot_pool_df.copy()
    hotspot_type = df["hotspot_type"] if "hotspot_type" in df.columns else pd.Series("", index=df.index)
    positive = df[hotspot_type.isin(["persistent_inflow", "reversal_to_inflow"])]
    pressure = df[hotspot_type.isin(["persistent_outflow", "worsening"])]
    key = _names_from_df(df, "theme_name", "abs_value_change", 3)
    return {
        "intraday_available": True,
        "intraday_summary_label": (hotspot_summary or {}).get("summary_label") or "日内热点分化",
        "positive_hotspots": _names_from_df(positive, "theme_name", "latest_value", 3),
        "pressure_hotspots": _names_from_df(pressure, "theme_name", "latest_value", 3),
        "key_intraday_themes": key,
        "intraday_summary_reason": (hotspot_summary or {}).get("summary_reason") or "当前日内主题资金结构分化。",
    }


def summarize_multi_day_for_brief(
    multi_day_summary: dict | None,
    multi_day_pool_df: pd.DataFrame | None,
) -> dict:
    date_count = _safe_int((multi_day_summary or {}).get("date_count"))
    if multi_day_pool_df is None or multi_day_pool_df.empty or date_count < 2:
        return {
            "multi_day_available": False,
            "multi_day_summary_label": "多日样本不足",
            "strength_trends": [],
            "pressure_trends": [],
            "key_multi_day_themes": [],
            "multi_day_summary_reason": "当前本地缓存日期不足，暂不做多日趋势判断。",
        }
    df = multi_day_pool_df.copy()
    trend_type = df["trend_type"] if "trend_type" in df.columns else pd.Series("", index=df.index)
    strength = df[trend_type.isin(["persistent_strength", "reversal_to_strength"])]
    pressure = df[trend_type.isin(["persistent_pressure", "weakening_trend"])]
    return {
        "multi_day_available": True,
        "multi_day_summary_label": (multi_day_summary or {}).get("summary_label") or "多日主题结构分化",
        "strength_trends": _names_from_df(strength, "theme_name", "latest_value", 3),
        "pressure_trends": _names_from_df(pressure, "theme_name", "latest_value", 3),
        "key_multi_day_themes": _names_from_df(df, "theme_name", "abs_value_change", 3),
        "multi_day_summary_reason": (multi_day_summary or {}).get("summary_reason") or "当前多个缓存日期中的主题资金状态分化。",
    }


def summarize_holding_pool_for_brief(
    fund_summary_df: pd.DataFrame | None,
    top_n: int = 3,
) -> dict:
    if fund_summary_df is None or fund_summary_df.empty:
        return {
            "holding_available": False,
            "strongest_funds": [],
            "pressured_funds": [],
            "holding_summary_label": "持仓相关池暂无数据",
            "holding_summary_reason": "当前暂无可用的手动基金主题配置或主题雷达结果。",
        }
    df = fund_summary_df.copy()
    df["weighted_impact_score"] = pd.to_numeric(df.get("weighted_impact_score"), errors="coerce").fillna(0)
    strongest = df.sort_values("weighted_impact_score", ascending=False)["fund_name"].dropna().astype(str).head(top_n).tolist()
    pressured = df.sort_values("weighted_impact_score", ascending=True)["fund_name"].dropna().astype(str).head(top_n).tolist()
    positive_count = int(df["weighted_impact_score"].gt(0.2).sum())
    pressure_count = int(df["weighted_impact_score"].lt(-0.2).sum())
    if positive_count > pressure_count:
        label = "关注组合相关主题偏强"
        reason = "手动配置的关注组合中，相关主题资金偏强的项目更多。"
    elif pressure_count > positive_count:
        label = "关注组合相关主题承压"
        reason = "手动配置的关注组合中，相关主题资金承压的项目更多。"
    else:
        label = "关注组合相关主题分化"
        reason = "手动配置的关注组合中，偏强和承压项目并存。"
    return {
        "holding_available": True,
        "strongest_funds": strongest,
        "pressured_funds": pressured,
        "holding_summary_label": label,
        "holding_summary_reason": reason,
    }


def summarize_taxonomy_coverage_for_brief(
    coverage_report: dict | None,
    consistency_report: dict | None,
) -> dict:
    if not coverage_report:
        return {
            "coverage_available": False,
            "coverage_label": "暂无覆盖审计",
            "coverage_ratio": 0.0,
            "high_flow_uncovered_count": 0,
            "overlap_warning_count": 0,
            "consistency_label": (consistency_report or {}).get("consistency_label", "--"),
            "coverage_summary_reason": "当前暂无可审计快照，暂不生成主题覆盖说明。",
        }
    ratio = _safe_float(coverage_report.get("coverage_ratio"))
    high_flow = coverage_report.get("high_flow_uncovered_df")
    duplicated = coverage_report.get("duplicated_sector_df")
    high_count = len(high_flow) if isinstance(high_flow, pd.DataFrame) else 0
    overlap_count = len(duplicated) if isinstance(duplicated, pd.DataFrame) else 0
    label = coverage_report.get("coverage_label") or "主题覆盖审计"
    reason = coverage_report.get("coverage_reason") or "当前主题库覆盖情况已生成。"
    if ratio < 0.4:
        reason += " 当前主题库定位为基金观察池，不等同于全市场行业分类，因此覆盖率偏低不代表数据异常。"
    return {
        "coverage_available": True,
        "coverage_label": label,
        "coverage_ratio": ratio,
        "high_flow_uncovered_count": high_count,
        "overlap_warning_count": overlap_count,
        "consistency_label": (consistency_report or {}).get("consistency_label", "--"),
        "coverage_summary_reason": reason,
    }


def build_observation_brief(
    data_context: dict,
    radar_summary: dict,
    intraday_summary: dict,
    multi_day_summary: dict,
    holding_summary: dict,
    coverage_summary: dict,
) -> dict:
    title = "养基宝主题资金流观察简报"
    subtitle = (
        f"{data_context.get('selected_date', '--')} ｜ {data_context.get('data_context_label', '--')} ｜ "
        f"{data_context.get('theme_mode_label', '--')}"
    )
    executive_sentences = [
        f"当前数据处于{data_context.get('data_context_label', '观察')}状态，{data_context.get('data_context_reason', '')}",
        f"主题雷达显示：{radar_summary.get('radar_summary_label', '主题资金分化')}，{radar_summary.get('radar_summary_reason', '')}",
    ]
    if intraday_summary.get("intraday_available"):
        executive_sentences.append(
            f"日内热点层显示：{intraday_summary.get('intraday_summary_label')}，{intraday_summary.get('intraday_summary_reason')}"
        )
    else:
        executive_sentences.append(intraday_summary.get("intraday_summary_reason", "当前样本不足，暂不做日内变化判断。"))
    if multi_day_summary.get("multi_day_available"):
        executive_sentences.append(
            f"多日趋势层显示：{multi_day_summary.get('multi_day_summary_label')}，{multi_day_summary.get('multi_day_summary_reason')}"
        )
    else:
        executive_sentences.append(multi_day_summary.get("multi_day_summary_reason", "当前本地缓存日期不足，暂不做多日趋势判断。"))

    key_points = [
        f"主题雷达：偏强主题 {radar_summary.get('positive_count', 0)} 个，承压主题 {radar_summary.get('negative_count', 0)} 个，中性主题 {radar_summary.get('neutral_count', 0)} 个。",
        f"偏强主题观察：{_join_names(radar_summary.get('strongest_themes', []))}。",
        f"承压主题观察：{_join_names(radar_summary.get('weakest_themes', []))}。",
        f"日内关键主题：{_join_names(intraday_summary.get('key_intraday_themes', []), '当前日内样本不足')}。",
        f"多日关键主题：{_join_names(multi_day_summary.get('key_multi_day_themes', []), '当前多日样本不足')}。",
        f"持仓相关池：{holding_summary.get('holding_summary_label', '暂无持仓相关观察')}。",
    ]
    risk_notes = [
        "主题口径存在上下级和交叉映射风险，广度观察不代表严格净流入。",
        f"主题覆盖状态：{coverage_summary.get('coverage_label', '--')}，高资金流未覆盖板块 {coverage_summary.get('high_flow_uncovered_count', 0)} 个。",
        "AKShare / 东方财富免费数据源可能受网络、接口变化和非交易时段影响。",
    ]
    if not intraday_summary.get("intraday_available"):
        risk_notes.append("当前快照数量不足，暂不做日内变化判断。")
    if not multi_day_summary.get("multi_day_available"):
        risk_notes.append("当前本地缓存日期不足，暂不做多日趋势判断。")
    data_notes = [
        f"数据日期：{data_context.get('selected_date', '--')}，最新时间：{data_context.get('latest_captured_time', '--:--:--')}。",
        f"视图状态：{data_context.get('view_status', '--')}，快照时间点：{data_context.get('captured_time_count', 0)}。",
        coverage_summary.get("coverage_summary_reason", "主题覆盖审计只用于解释归并质量。"),
    ]
    disclaimer = "本简报仅用于学习研究和可视化观察，不构成投资建议，不预测未来走势。"
    return {
        "brief_title": title,
        "brief_subtitle": subtitle,
        "executive_summary": "".join(item for item in executive_sentences if item)[:520],
        "key_points": [item for item in key_points if item][:6],
        "risk_notes": risk_notes[:4],
        "data_notes": data_notes[:4],
        "disclaimer": disclaimer,
    }


def render_brief_markdown(brief: dict) -> str:
    title = brief.get("brief_title") or "养基宝主题资金流观察简报"
    subtitle = brief.get("brief_subtitle") or ""
    lines = [
        f"# {title}",
        "",
        subtitle,
        "",
        "## 一、摘要",
        "",
        brief.get("executive_summary") or "暂无可用摘要。",
        "",
        "## 二、关键观察",
        "",
    ]
    for item in brief.get("key_points") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## 三、口径与数据说明", ""])
    for item in (brief.get("risk_notes") or []) + (brief.get("data_notes") or []):
        lines.append(f"- {item}")
    lines.extend(["", "## 四、免责声明", "", brief.get("disclaimer") or ""])
    return "\n".join(lines).strip() + "\n"


def validate_brief_text(text: str) -> list[str]:
    hits = []
    for pattern in FORBIDDEN_BRIEF_PATTERNS:
        if re.search(re.escape(pattern), text or ""):
            hits.append(pattern)
    return sorted(set(hits), key=hits.index)
