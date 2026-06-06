from __future__ import annotations

import re
from typing import Any


FORBIDDEN_THEME_HISTORY_BRIEF_WORDS = (
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
    "建议关注",
)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _unique(items: list[str], limit: int | None = None) -> list[str]:
    seen = set()
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if limit and len(out) >= limit:
            break
    return out


def _is_sample_context(source_type: str | None, summary_reason: str | None = None) -> bool:
    source = str(source_type or "").upper()
    reason = str(summary_reason or "")
    return source == "SAMPLE" or ("SAMPLE" in source and "LOCAL" not in source) or "SAMPLE" in reason


def build_theme_history_brief_context(
    theme_history_summary: dict | None,
    quality_report: dict | None = None,
    visual_summary: dict | None = None,
    source_type: str | None = None,
    theme_mode: str | None = None,
    latest_per_day: bool = True,
) -> dict:
    summary = theme_history_summary or {}
    quality = quality_report or {}
    visual = visual_summary or {}
    available = bool(summary.get("history_available"))
    normalized_source = str(source_type or "ALL").upper()
    reason = str(summary.get("summary_reason") or "")
    sample_only = _is_sample_context(normalized_source, reason)
    if sample_only:
        data_notice = "当前主题历史摘要基于 SAMPLE 合成演示数据生成，仅用于展示主题历史聚合流程，不代表真实行情。"
    elif not available:
        data_notice = "当前暂无可用 warehouse 主题历史摘要；观察简报仍可基于当前页面数据正常生成。"
    elif normalized_source == "LOCAL":
        data_notice = "当前主题历史摘要基于 LOCAL 本地真实缓存索引生成，请注意 CSV 缓存时间和样本范围。"
    elif normalized_source == "ALL":
        data_notice = "当前主题历史摘要可能包含多个 source_type，解释时应区分 LOCAL 与 SAMPLE 的数据来源。"
    else:
        data_notice = "当前主题历史摘要基于已导入 warehouse 的历史快照生成。"

    return {
        "history_brief_available": available,
        "source_type": normalized_source,
        "theme_mode": theme_mode or "--",
        "latest_per_day": bool(latest_per_day),
        "date_count": int(summary.get("date_count", 0) or quality.get("date_count", 0) or 0),
        "theme_count": int(summary.get("theme_count", 0) or quality.get("theme_count", 0) or 0),
        "latest_date": summary.get("latest_date") or "--",
        "summary_label": summary.get("summary_label") or "暂无主题历史摘要",
        "summary_reason": reason or "当前暂无可用主题历史摘要。",
        "strongest_latest_themes": _as_list(summary.get("strongest_latest_themes")),
        "pressured_latest_themes": _as_list(summary.get("pressured_latest_themes")),
        "consistent_positive_themes": _as_list(summary.get("most_consistent_positive_themes")),
        "consistent_pressure_themes": _as_list(summary.get("most_consistent_pressure_themes")),
        "high_variation_themes": _as_list(summary.get("high_variation_themes")),
        "quality_label": quality.get("quality_label") or "--",
        "visual_summary_label": visual.get("visual_summary_label") or "--",
        "data_notice": data_notice,
        "warnings": _as_list(summary.get("warnings")) + _as_list(quality.get("warnings")) + _as_list(visual.get("warnings")),
        "errors": _as_list(summary.get("errors")) + _as_list(quality.get("errors")) + _as_list(visual.get("errors")),
    }


def build_theme_history_brief_points(context: dict, max_points: int = 4) -> list[str]:
    if not context or not context.get("history_brief_available"):
        return ["当前暂无可用 warehouse 主题历史摘要，观察简报仍保留当前主题雷达、日内热点和多日趋势说明。"]
    points: list[str] = []
    date_count = int(context.get("date_count", 0) or 0)
    theme_count = int(context.get("theme_count", 0) or 0)
    points.append(f"从已导入 warehouse 的历史快照看，本次主题历史样本覆盖 {date_count} 个日期、{theme_count} 个主题。")
    strongest = _unique(_as_list(context.get("strongest_latest_themes")), 3)
    if strongest:
        points.append(f"最新样本中资金偏强的主题包括：{'、'.join(strongest)}。")
    pressured = _unique(_as_list(context.get("pressured_latest_themes")), 3)
    if pressured:
        points.append(f"最新样本中资金承压的主题包括：{'、'.join(pressured)}。")
    variation = _unique(_as_list(context.get("high_variation_themes")), 3)
    if variation:
        points.append(f"样本内波动较明显的主题包括：{'、'.join(variation)}，该描述仅反映已导入历史快照。")
    if "SAMPLE" in str(context.get("data_notice", "")):
        points.append("当前样本主要来自 SAMPLE 合成演示数据，仅用于展示主题历史聚合流程。")
    if date_count < 3:
        points.append("样本日期较少，暂不做趋势判断。")
    return _unique(points, max(1, min(int(max_points or 4), 6)))


def build_theme_history_brief_risk_notes(context: dict, max_notes: int = 4) -> list[str]:
    notes = [
        "CSV 仍是 source of truth；SQLite warehouse 只是本地可重建查询索引。",
        "主题历史摘要只描述已导入历史快照中的资金状态，不预测未来走势。",
        "本摘要不构成投资建议，也不包含交易操作指引。",
    ]
    if context and context.get("latest_per_day"):
        notes.append("latest_per_day=True 时，每个日期只取最新 captured_time 参与主题历史摘要。")
    if context and "SAMPLE" in str(context.get("data_notice", "")):
        notes.append("SAMPLE 合成演示数据不代表真实行情。")
    if context and int(context.get("date_count", 0) or 0) < 3:
        notes.append("样本日期较少时，仅适合演示历史聚合流程。")
    return _unique(notes, max(1, min(int(max_notes or 4), 6)))


def render_theme_history_brief_section(context: dict, heading_level: int = 2) -> str:
    level = max(2, min(int(heading_level or 2), 4))
    heading = "#" * level
    subheading = "#" * min(level + 1, 6)
    lines = [f"{heading} 主题历史观察摘要", ""]
    if not context or not context.get("history_brief_available"):
        lines.extend(
            [
                f"{subheading} 历史样本概览",
                "",
                "当前暂无可用 warehouse 主题历史摘要。观察简报仍可基于当前主题雷达、日内热点、多日趋势和持仓相关池正常生成。",
                "",
                f"{subheading} 样本与口径限制",
                "",
                "- CSV 仍是 source of truth；SQLite warehouse 只是本地可重建查询索引。",
                "- 主题历史摘要不会自动重建 warehouse，也不会写入 SQLite 或 CSV。",
                "- 本简报不预测未来走势，不构成投资建议。",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    lines.extend(
        [
            f"{subheading} 历史样本概览",
            "",
            f"- 数据来源：{context.get('source_type', '--')}",
            f"- 主题口径：{context.get('theme_mode', '--')}",
            f"- 样本日期数：{context.get('date_count', 0)}",
            f"- 覆盖主题数：{context.get('theme_count', 0)}",
            f"- 最新样本日期：{context.get('latest_date', '--')}",
            f"- 摘要状态：{context.get('summary_label', '--')}",
            f"- 数据声明：{context.get('data_notice', '')}",
            "",
            f"{subheading} 主题历史观察",
            "",
        ]
    )
    lines.extend(f"- {point}" for point in build_theme_history_brief_points(context))
    lines.extend(["", f"{subheading} 样本与口径限制", ""])
    lines.extend(f"- {note}" for note in build_theme_history_brief_risk_notes(context))
    return "\n".join(lines).strip() + "\n"


def merge_theme_history_section_into_markdown(
    markdown_text: str,
    theme_history_section: str,
    insert_after_heading: str = "## 三、主题与持仓相关观察",
) -> str:
    base = str(markdown_text or "").strip()
    section = str(theme_history_section or "").strip()
    if not section:
        return base + ("\n" if base else "")
    if not base:
        return section + "\n"

    heading_index = base.find(insert_after_heading)
    if heading_index >= 0:
        next_heading = re.search(r"\n##\s+", base[heading_index + len(insert_after_heading) :])
        if next_heading:
            insert_pos = heading_index + len(insert_after_heading) + next_heading.start()
            return (base[:insert_pos].rstrip() + "\n\n" + section + "\n\n" + base[insert_pos:].lstrip()).strip() + "\n"
        return (base.rstrip() + "\n\n" + section).strip() + "\n"

    disclaimer_index = base.find("## 六、免责声明")
    if disclaimer_index >= 0:
        return (base[:disclaimer_index].rstrip() + "\n\n" + section + "\n\n" + base[disclaimer_index:].lstrip()).strip() + "\n"
    return (base.rstrip() + "\n\n" + section).strip() + "\n"


def validate_theme_history_brief_text(text: str) -> list[str]:
    hits = []
    for pattern in FORBIDDEN_THEME_HISTORY_BRIEF_WORDS:
        if pattern in str(text or ""):
            hits.append(pattern)
    return sorted(set(hits), key=hits.index)


def build_theme_history_brief_compliance_report(text: str) -> dict:
    text = str(text or "")
    forbidden_hits = validate_theme_history_brief_text(text)
    has_sample_notice = "SAMPLE" in text and "合成演示数据" in text
    has_no_prediction_notice = "不预测未来走势" in text
    has_no_advice_notice = "不构成投资建议" in text
    has_source_of_truth_notice = "source of truth" in text or "CSV 仍是主数据来源" in text
    if forbidden_hits:
        label = "存在禁词风险"
        reason = "主题历史摘要命中动作性或预测性表达，已阻止导出。"
    elif not (has_no_prediction_notice and has_no_advice_notice and has_source_of_truth_notice):
        label = "存在轻微缺失"
        reason = "主题历史摘要缺少部分非预测、免责声明或 CSV-first 说明。"
    else:
        label = "合规通过"
        reason = "主题历史摘要包含数据边界、非预测和非投资建议说明，未命中禁词。"
    return {
        "forbidden_hits": forbidden_hits,
        "has_sample_notice": has_sample_notice,
        "has_no_prediction_notice": has_no_prediction_notice,
        "has_no_advice_notice": has_no_advice_notice,
        "has_source_of_truth_notice": has_source_of_truth_notice,
        "compliance_label": label,
        "compliance_reason": reason,
    }
