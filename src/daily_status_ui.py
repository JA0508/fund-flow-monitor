import streamlit as st

from src.market_session_policy import evaluate_market_session_date


def render_daily_status(view_mode: str, cache: dict, audit: dict) -> None:
    """Display existing cache evidence without upgrading it to readiness."""
    st.subheader("每日数据状态")
    if view_mode in {"SAMPLE", "DEMO"}:
        st.info(f"当前展示 {view_mode}，不代表真实行情；下方单独列出本地真实缓存状态。")
    states = {
        "today": "今日日期（未验证可用性）",
        "historical": "历史缓存",
        "future": "未来日期（不可作为今日行情）",
        "missing": "无真实缓存",
        "unknown": "日期未知",
    }
    audit_status = audit.get("latest_run_status")
    if not audit_status:
        audit_status = "采集记录不可验证" if audit.get("log_exists") else "无运行记录"
    fields = [
        ("当前视图", view_mode),
        ("真实缓存日期", cache.get("latest_snapshot_date")),
        ("日期状态", states.get(cache.get("staleness_status"), "日期未知")),
        ("捕获时间", cache.get("latest_captured_time")),
        ("来源", cache.get("latest_source") or cache.get("latest_provider")),
        ("质量标签", cache.get("quality_label")),
        ("质量与缺失原因", cache.get("quality_reason")),
        ("最近可读采集结果", audit_status),
        ("采集运行时间", audit.get("latest_run_timestamp")),
    ]
    st.text("\n".join(f"{label}：{value or '未提供'}" for label, value in fields))
    if audit.get("warning_count") or audit.get("malformed_line_count"):
        st.warning("采集日志读取或解析存在异常；可读记录不保证包含最近一次运行，请检查本地采集日志。")
    st.caption("今日日期或采集成功均不证明数据完整、来源合格或交易日历已验证；最近采集记录也不一定对应当前缓存。")
    calendar = evaluate_market_session_date(cache.get("latest_snapshot_date"))
    start = calendar.get("calendar_coverage_start") or "未声明"
    end = calendar.get("calendar_coverage_end") or "未声明"
    st.text(
        f"缓存日期日历校验：{calendar['market_session_date_state']}\n"
        f"日历覆盖范围：{start} 至 {end}\n"
        f"日历来源：{calendar['calendar_source_identity']}\n"
        f"校验原因：{calendar['decision_reason']}"
    )
    st.caption("日历为项目离线 provider-derived 参考，非交易所权威日历；日期合格不代表来源和数据质量合格。")
