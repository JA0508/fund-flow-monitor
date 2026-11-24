from __future__ import annotations


def render_daily_brief(selected_date: str | None, data_status: str, snapshot: dict) -> str:
    """Render only the selected theme, retaining every supplied evidence limit."""
    evidence_date = snapshot.get("as_of_trade_date")
    date_mismatch = bool(evidence_date and evidence_date != selected_date)
    state = "证据日期与所选日期不一致，暂不展示主题状态。" if date_mismatch else str(
        snapshot.get("observed_state") or "暂无可用主题状态"
    )
    lines = [
        f"# {selected_date or '日期未验证'} · {snapshot.get('theme_name') or '关注主题'}",
        f"数据状态：{data_status}",
        "",
        state,
        f"证据日期：{evidence_date or '未验证'}；捕获时间：{snapshot.get('as_of_captured_time') or '未提供'}",
    ]
    for key in ("source_notice", "member_coverage_label", "history_readiness_label", "history_scope_notice"):
        if snapshot.get(key):
            lines.append(str(snapshot[key]))
    limitations = snapshot.get("limitations") or []
    if limitations:
        lines.extend(["", "## 观察限制", *[f"- {item}" for item in limitations]])
    lines.extend(["", "仅描述已保存状态，不构成投资建议。"])
    return "\n\n".join(lines)
