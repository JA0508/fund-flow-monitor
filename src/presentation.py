from __future__ import annotations


STANDARD_MODE = "标准模式"
PORTFOLIO_MODE = "作品集演示模式"

FORBIDDEN_WORDS = (
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
)


def get_display_mode_options() -> list[str]:
    return [STANDARD_MODE, PORTFOLIO_MODE]


def normalize_display_mode(mode: str | None) -> str:
    value = str(mode or "").strip()
    return value if value in get_display_mode_options() else STANDARD_MODE


def is_portfolio_mode(mode: str | None) -> bool:
    return normalize_display_mode(mode) == PORTFOLIO_MODE


def should_show_debug_details(mode: str | None) -> bool:
    return not is_portfolio_mode(mode)


def build_status_badge_config(view_status: str) -> dict:
    status = str(view_status or "unknown").upper()
    configs = {
        "LIVE": {
            "label": "实时行情",
            "short_label": "LIVE",
            "tone": "success",
            "description": "本轮刷新成功抓取 AKShare 数据，并使用本轮快照。",
            "is_real_market_data": True,
            "is_demo_like": False,
            "should_show_warning": False,
        },
        "CACHE": {
            "label": "真实缓存",
            "short_label": "CACHE",
            "tone": "info",
            "description": "当前展示本地真实 CSV 缓存，不代表本轮实时抓取成功。",
            "is_real_market_data": True,
            "is_demo_like": False,
            "should_show_warning": False,
        },
        "HISTORY": {
            "label": "历史回放",
            "short_label": "HISTORY",
            "tone": "purple",
            "description": "当前展示所选日期的本地真实 CSV 历史缓存，不代表实时行情。",
            "is_real_market_data": True,
            "is_demo_like": False,
            "should_show_warning": True,
        },
        "SAMPLE": {
            "label": "SAMPLE 合成演示数据",
            "short_label": "SAMPLE",
            "tone": "warning",
            "description": "当前展示仓库内置合成样例数据，仅用于演示页面功能，不代表真实行情。",
            "is_real_market_data": False,
            "is_demo_like": True,
            "should_show_warning": True,
        },
        "DEMO": {
            "label": "DEMO 内存模拟数据",
            "short_label": "DEMO",
            "tone": "warning",
            "description": "当前展示内存模拟数据，仅用于 UI 调试，不代表真实行情。",
            "is_real_market_data": False,
            "is_demo_like": True,
            "should_show_warning": True,
        },
        "EMPTY": {
            "label": "暂无可用数据",
            "short_label": "EMPTY",
            "tone": "danger",
            "description": "当前暂无可用真实缓存或样例数据。",
            "is_real_market_data": False,
            "is_demo_like": False,
            "should_show_warning": True,
        },
    }
    base = configs.get(
        status,
        {
            "label": "未知数据状态",
            "short_label": status or "UNKNOWN",
            "tone": "neutral",
            "description": "当前数据状态未识别，请检查状态传递逻辑。",
            "is_real_market_data": False,
            "is_demo_like": False,
            "should_show_warning": True,
        },
    ).copy()
    base["status"] = status
    return base


def build_portfolio_intro_context(
    app_version: str,
    view_status: str,
    selected_date: str | None,
    display_mode: str,
) -> dict:
    status_badge = build_status_badge_config(view_status)
    return {
        "title": "养基宝主题资金流雷达",
        "subtitle": "面向基金投资辅助的 A 股主题资金流观察仪表盘",
        "value_proposition": (
            "将原始行业/概念资金流归并为基金用户更容易理解的主题状态，"
            "用于学习研究、可视化展示和作品集演示。"
        ),
        "status_badge": status_badge,
        "selected_date": selected_date or "--",
        "mode_label": normalize_display_mode(display_mode),
        "app_version": app_version,
        "key_capabilities": [
            "主题雷达",
            "日内热点",
            "多日趋势",
            "持仓相关池",
            "观察简报",
            "SAMPLE 可复现演示",
            "CSV 快照质量治理",
        ],
        "boundary_notes": [
            "不做交易",
            "不做买卖建议",
            "不预测未来走势",
            "SAMPLE / DEMO 不代表真实行情",
        ],
    }


def build_screenshot_checklist() -> list[dict]:
    return [
        {
            "screenshot_name": "home_overview.png",
            "target_tab": "实时曲线",
            "recommended_mode": PORTFOLIO_MODE,
            "recommended_data_source": "SAMPLE",
            "what_to_capture": "顶部状态 badge、项目 intro、主力资金曲线。",
            "notes": "突出 SAMPLE 合成演示数据，不展示本地真实路径。",
        },
        {
            "screenshot_name": "theme_radar.png",
            "target_tab": "主题雷达",
            "recommended_mode": PORTFOLIO_MODE,
            "recommended_data_source": "SAMPLE",
            "what_to_capture": "今日资金温度、关注主题雷达、主题库状态。",
            "notes": "保留主题口径说明和非投资建议边界。",
        },
        {
            "screenshot_name": "intraday_hotspots.png",
            "target_tab": "日内热点",
            "recommended_mode": PORTFOLIO_MODE,
            "recommended_data_source": "SAMPLE",
            "what_to_capture": "日内热点概览、流入/修复主题、承压/走弱主题。",
            "notes": "SAMPLE 日期应有多个 captured_time。",
        },
        {
            "screenshot_name": "multi_day_trends.png",
            "target_tab": "多日趋势",
            "recommended_mode": PORTFOLIO_MODE,
            "recommended_data_source": "SAMPLE",
            "what_to_capture": "多日趋势概览、趋势分区和深色明细表。",
            "notes": "SAMPLE 目录至少包含两个日期。",
        },
        {
            "screenshot_name": "theme_history_visuals.png",
            "target_tab": "多日趋势",
            "recommended_mode": PORTFOLIO_MODE,
            "recommended_data_source": "SAMPLE",
            "what_to_capture": "Warehouse 主题历史图表、source_type 控件和 SAMPLE 说明。",
            "notes": "截图应明确图表来自合成演示数据，不代表真实行情。",
        },
        {
            "screenshot_name": "holding_pool.png",
            "target_tab": "持仓相关池",
            "recommended_mode": PORTFOLIO_MODE,
            "recommended_data_source": "SAMPLE",
            "what_to_capture": "基金摘要卡片、主题暴露明细、CSV 模板说明。",
            "notes": "强调手动主题配置，不是账户持仓。",
        },
        {
            "screenshot_name": "observation_brief.png",
            "target_tab": "观察简报",
            "recommended_mode": PORTFOLIO_MODE,
            "recommended_data_source": "SAMPLE",
            "what_to_capture": "摘要、关键观察、口径说明、Markdown 下载。",
            "notes": "免责声明必须可见。",
        },
        {
            "screenshot_name": "data_quality.png",
            "target_tab": "数据说明",
            "recommended_mode": PORTFOLIO_MODE,
            "recommended_data_source": "SAMPLE",
            "what_to_capture": "CSV 快照数据质量、本地/SAMPLE 质量概览。",
            "notes": "避免暴露真实私有路径。",
        },
        {
            "screenshot_name": "sample_mode.png",
            "target_tab": "实时曲线",
            "recommended_mode": PORTFOLIO_MODE,
            "recommended_data_source": "SAMPLE",
            "what_to_capture": "SAMPLE 状态 badge 和样例数据说明。",
            "notes": "明确 SAMPLE 不代表真实行情。",
        },
    ]


def build_demo_walkthrough_steps() -> list[dict]:
    return [
        {
            "step_title": "选择 SAMPLE 演示数据",
            "target_tab": "侧边栏",
            "description": "切换到演示样例数据，确保无网络、无真实缓存时也能完整体验。",
            "expected_user_takeaway": "项目具备可复现展示路径。",
        },
        {
            "step_title": "查看实时曲线",
            "target_tab": "实时曲线",
            "description": "观察主题资金流曲线、数据状态和快照时间点。",
            "expected_user_takeaway": "理解主图如何展示资金流时间序列。",
        },
        {
            "step_title": "查看主题雷达",
            "target_tab": "主题雷达",
            "description": "查看基金观察主题、资金温度和核心/广度分歧提示。",
            "expected_user_takeaway": "理解项目如何把原始板块转译为基金主题。",
        },
        {
            "step_title": "查看日内热点和多日趋势",
            "target_tab": "日内热点 / 多日趋势",
            "description": "观察同日和跨日期的主题资金状态变化。",
            "expected_user_takeaway": "理解快照沉淀后的解释层价值。",
        },
        {
            "step_title": "查看持仓相关池",
            "target_tab": "持仓相关池",
            "description": "查看 JSON 配置和 SAMPLE CSV 主题暴露模板如何映射到主题雷达。",
            "expected_user_takeaway": "理解关注组合与主题资金状态的连接方式。",
        },
        {
            "step_title": "下载观察简报",
            "target_tab": "观察简报",
            "description": "生成并下载 Markdown 观察简报。",
            "expected_user_takeaway": "理解统一解释层和导出能力。",
        },
        {
            "step_title": "检查数据质量面板",
            "target_tab": "数据说明",
            "description": "查看 CSV 快照质量、主题库治理和截图指南。",
            "expected_user_takeaway": "理解项目的数据可信边界。",
        },
    ]


def validate_presentation_text(text: str) -> list[str]:
    content = str(text or "")
    return [word for word in FORBIDDEN_WORDS if word in content]
