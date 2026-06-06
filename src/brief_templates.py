from __future__ import annotations

import re
from typing import Any

from src.config import APP_VERSION
from src.utils import get_china_now


STANDARD_BRIEF_MODE = "标准简报"
PORTFOLIO_BRIEF_MODE = "作品集演示简报"
BRIEF_TEMPLATE_MODES = (STANDARD_BRIEF_MODE, PORTFOLIO_BRIEF_MODE)

FORBIDDEN_BRIEF_TEMPLATE_PATTERNS = (
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


def get_brief_template_modes() -> list[str]:
    return list(BRIEF_TEMPLATE_MODES)


def normalize_brief_template_mode(mode: str | None) -> str:
    return mode if mode in BRIEF_TEMPLATE_MODES else STANDARD_BRIEF_MODE


def is_portfolio_brief_mode(mode: str | None) -> bool:
    return normalize_brief_template_mode(mode) == PORTFOLIO_BRIEF_MODE


def build_brief_template_config(mode: str | None) -> dict:
    normalized = normalize_brief_template_mode(mode)
    portfolio = is_portfolio_brief_mode(normalized)
    return {
        "mode": normalized,
        "title": "养基宝主题资金流观察简报",
        "subtitle": "基金主题资金流观察层" if not portfolio else "SAMPLE 可复现演示版",
        "include_metadata": True,
        "include_demo_notice": portfolio,
        "include_method_notes": True,
        "include_release_notes": portfolio,
        "section_order": [
            "摘要",
            "关键观察",
            "主题与持仓相关观察",
            "口径与数据说明",
            "样本与限制",
            "免责声明",
        ]
        + (["项目展示说明"] if portfolio else []),
        "tone_label": "克制简洁" if not portfolio else "作品集展示",
    }


def _normalize_status(view_status: str | None) -> str:
    status = str(view_status or "EMPTY").strip().upper()
    return status if status in {"LIVE", "CACHE", "HISTORY", "SAMPLE", "DEMO", "EMPTY"} else "EMPTY"


def build_brief_metadata(
    selected_date: str | None,
    view_status: str,
    theme_mode_label: str | None = None,
    app_version: str | None = None,
    source_label: str | None = None,
) -> dict:
    status = _normalize_status(view_status)
    is_real_market_data = status in {"LIVE", "CACHE", "HISTORY"}
    if status == "SAMPLE":
        data_notice = "当前简报基于仓库内置合成样例数据生成，不代表真实行情。"
    elif status == "DEMO":
        data_notice = "当前简报基于内存模拟数据生成，不代表真实行情。"
    elif status == "LIVE":
        data_notice = "当前简报基于本轮成功抓取的真实数据源生成，请注意免费数据源可能存在时延和上游波动。"
    elif status == "CACHE":
        data_notice = "当前简报基于本地真实缓存生成，请注意缓存时间和数据时效性。"
    elif status == "HISTORY":
        data_notice = "当前简报基于本地真实历史缓存回放生成，不代表实时行情。"
    else:
        data_notice = "当前暂无可用真实数据，简报仅保留数据状态说明。"
    return {
        "generated_at": get_china_now().strftime("%Y-%m-%d %H:%M:%S"),
        "selected_date": selected_date or "--",
        "view_status": status,
        "theme_mode_label": theme_mode_label or "--",
        "app_version": app_version or APP_VERSION,
        "source_label": source_label or ("真实数据 / 本地缓存" if is_real_market_data else status),
        "is_real_market_data": is_real_market_data,
        "data_notice": data_notice,
    }


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _bullet_lines(items: list[str], empty: str) -> list[str]:
    values = [item for item in items if item]
    if not values:
        values = [empty]
    return [f"- {item}" for item in values]


def _unique_items(items: list[str]) -> list[str]:
    seen = set()
    unique = []
    for item in items:
        key = str(item).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(key)
    return unique


def _metadata_lines(metadata: dict) -> list[str]:
    if not metadata:
        return []
    return [
        f"- 生成时间：{metadata.get('generated_at', '--')}",
        f"- 数据日期：{metadata.get('selected_date', '--')}",
        f"- 数据状态：{metadata.get('view_status', '--')}",
        f"- 主题口径：{metadata.get('theme_mode_label', '--')}",
        f"- 应用版本：{metadata.get('app_version', '--')}",
        f"- 数据来源：{metadata.get('source_label', '--')}",
    ]


def render_brief_markdown_v2(
    brief: dict,
    template_mode: str | None = None,
    metadata: dict | None = None,
) -> str:
    config = build_brief_template_config(template_mode)
    metadata = metadata or {}
    title = config["title"]
    subtitle = brief.get("brief_subtitle") or config["subtitle"]
    data_notice = metadata.get("data_notice") or "当前简报仅解释已展示或已缓存的资金流状态。"
    lines: list[str] = [
        f"# {title}",
        "",
        f"> {data_notice} 本简报仅用于学习研究和可视化观察，不预测未来走势，不构成投资建议。",
        "",
        subtitle,
        "",
    ]
    if config["include_metadata"]:
        lines.extend(["**简报元信息**", ""])
        lines.extend(_metadata_lines(metadata))
        lines.append("")

    lines.extend(["## 一、摘要", "", brief.get("executive_summary") or "暂无可用摘要。", ""])
    lines.extend(["## 二、关键观察", ""])
    lines.extend(_bullet_lines(_as_list(brief.get("key_points")), "暂无明确关键观察。"))
    lines.extend(["", "## 三、主题与持仓相关观察", ""])
    holding_items = [
        item
        for item in _as_list(brief.get("key_points"))
        if ("持仓" in item or "主题雷达" in item or "日内" in item or "多日" in item)
    ]
    if not holding_items:
        holding_items = [
            "主题雷达、日内热点、多日趋势和持仓相关池共同用于解释已发生的资金流状态。",
        ]
    lines.extend(_bullet_lines(holding_items[:5], "暂无主题与持仓相关观察。"))

    lines.extend(["", "## 四、口径与数据说明", ""])
    lines.extend(_bullet_lines(_as_list(brief.get("data_notes")), "暂无额外数据说明。"))
    if config["include_method_notes"]:
        lines.extend(
            [
                "- 主题口径用于将原始行业/概念板块归并为基金观察主题，不等同于正式行业分类。",
                "- 广度观察可能包含上下级板块重叠，不能直接理解为严格净流入。",
            ]
        )

    lines.extend(["", "## 五、样本与限制", ""])
    limit_items = _unique_items(
        _as_list(brief.get("risk_notes"))
        + [
            "日内热点和多日趋势只解释已有快照中的历史状态，不预测未来走势。",
            "AKShare / 东方财富免费数据源可能受网络、接口变化和非交易时段影响。",
        ]
    )
    lines.extend(_bullet_lines(limit_items, "暂无额外样本限制说明。"))

    lines.extend(["", "## 六、免责声明", "", brief.get("disclaimer") or "本简报仅用于学习研究和可视化观察，不构成投资建议，不预测未来走势。"])

    if config["include_release_notes"]:
        lines.extend(
            [
                "",
                "## 七、项目展示说明",
                "",
                "- 本简报由 SAMPLE 合成演示数据生成，用于展示项目如何把行业/概念资金流转译成基金主题观察。",
                "- SAMPLE 数据来自仓库内置合成 CSV，不代表真实行情。",
                "- 作品集演示简报不改变底层计算结果，只调整 Markdown 展示结构。",
                "- 项目当前仍是 Streamlit + CSV MVP，不包含交易功能，也不预测未来走势。",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def render_brief_markdown_with_extra_sections(
    brief: dict,
    template_mode: str | None = None,
    metadata: dict | None = None,
    extra_sections: list[str] | None = None,
) -> str:
    """Render the existing v2 brief and insert optional markdown sections.

    Extra sections are inserted before the sample/limitation section when possible.
    The base rendering remains delegated to render_brief_markdown_v2 for backward
    compatibility with existing tests and downloads.
    """
    markdown = render_brief_markdown_v2(brief, template_mode=template_mode, metadata=metadata)
    sections = [str(section).strip() for section in (extra_sections or []) if str(section).strip()]
    if not sections:
        return markdown
    insert_block = "\n\n".join(sections)
    theme_marker = "## 三、主题与持仓相关观察"
    if theme_marker in markdown:
        start = markdown.index(theme_marker)
        next_heading = re.search(r"\n##\s+", markdown[start + len(theme_marker) :])
        if next_heading:
            insert_pos = start + len(theme_marker) + next_heading.start()
            return (markdown[:insert_pos].rstrip() + "\n\n" + insert_block + "\n\n" + markdown[insert_pos:].lstrip()).strip() + "\n"
    marker = "## 五、样本与限制"
    if marker in markdown:
        before, after = markdown.split(marker, 1)
        return (before.rstrip() + "\n\n" + insert_block + "\n\n" + marker + after).strip() + "\n"
    disclaimer = "## 六、免责声明"
    if disclaimer in markdown:
        before, after = markdown.split(disclaimer, 1)
        return (before.rstrip() + "\n\n" + insert_block + "\n\n" + disclaimer + after).strip() + "\n"
    return (markdown.rstrip() + "\n\n" + insert_block).strip() + "\n"


def validate_brief_template_text(text: str) -> list[str]:
    hits = []
    for pattern in FORBIDDEN_BRIEF_TEMPLATE_PATTERNS:
        if re.search(re.escape(pattern), text or ""):
            hits.append(pattern)
    return sorted(set(hits), key=hits.index)


def build_brief_compliance_report(text: str) -> dict:
    forbidden_hits = validate_brief_template_text(text)
    section_count = len(re.findall(r"^##\s+", text or "", flags=re.MULTILINE))
    has_required_disclaimer = "不构成投资建议" in (text or "")
    has_data_notice = any(token in (text or "") for token in ("数据声明", "SAMPLE", "合成演示数据", "真实缓存", "数据状态"))
    has_no_prediction_notice = "不预测未来走势" in (text or "")
    has_no_advice_notice = has_required_disclaimer
    if forbidden_hits:
        label = "存在禁词风险"
        reason = "简报中命中动作性表达，已阻止导出。"
    elif not (has_required_disclaimer and has_data_notice and has_no_prediction_notice):
        label = "存在轻微缺失"
        reason = "简报缺少部分数据声明或免责声明字段。"
    else:
        label = "合规通过"
        reason = "简报包含数据声明、免责声明和非预测说明，未命中动作性表达。"
    return {
        "forbidden_hits": forbidden_hits,
        "has_required_disclaimer": has_required_disclaimer,
        "has_data_notice": has_data_notice,
        "has_no_prediction_notice": has_no_prediction_notice,
        "has_no_advice_notice": has_no_advice_notice,
        "section_count": section_count,
        "compliance_label": label,
        "compliance_reason": reason,
    }


def validate_brief_markdown_structure(text: str) -> dict:
    text = text or ""
    checks = {
        "标题": "# 养基宝主题资金流观察简报" in text,
        "摘要": "## 一、摘要" in text,
        "关键观察": "## 二、关键观察" in text,
        "口径与数据说明": "## 四、口径与数据说明" in text,
        "免责声明": "## 六、免责声明" in text,
        "不构成投资建议": "不构成投资建议" in text,
        "不预测未来走势": "不预测未来走势" in text,
    }
    if "SAMPLE" in text or "合成演示数据" in text:
        checks["SAMPLE说明"] = "SAMPLE" in text or "合成演示数据" in text
    missing = [name for name, ok in checks.items() if not ok]
    warnings = [f"缺少 {name}" for name in missing]
    return {
        "is_valid": not missing,
        "missing_sections": missing,
        "warning_count": len(warnings),
        "warnings": warnings,
    }


def generate_brief_filename(
    selected_date: str | None,
    template_mode: str | None = None,
    suffix: str = "md",
) -> str:
    safe_date = "".join(ch for ch in str(selected_date or "unknown_date") if ch.isdigit() or ch == "-") or "unknown_date"
    safe_suffix = (suffix or "md").lstrip(".")
    prefix = "yangjibao_demo_brief" if is_portfolio_brief_mode(template_mode) else "yangjibao_brief"
    return f"{prefix}_{safe_date}.{safe_suffix}"
