from src.daily_brief import render_daily_brief


def test_short_brief_preserves_date_theme_and_all_limits():
    snapshot = {
        "theme_name": "医药", "observed_state": "数据不足",
        "source_notice": "来源日期未验证", "history_scope_notice": "单点快照",
        "limitations": ["旧数据", "采集失败"],
    }
    result = render_daily_brief("2026-11-03", "HISTORY", snapshot)
    for expected in ("2026-11-03", "医药", "HISTORY", "来源日期未验证", "单点快照", "旧数据", "采集失败"):
        assert expected in result
    assert "排行榜" not in result


def test_missing_snapshot_is_not_presented_as_available():
    assert "暂无可用主题状态" in render_daily_brief(None, "EMPTY", {})


def test_brief_shows_evidence_time_and_coverage():
    result = render_daily_brief("2026-11-03", "HISTORY", {
        "as_of_trade_date": "2026-11-03", "as_of_captured_time": "13:17:12",
        "member_coverage_label": "匹配 2/5 个成员",
        "history_readiness_label": "仅一个快照",
    })
    assert "13:17:12" in result
    assert "匹配 2/5 个成员" in result
    assert "仅一个快照" in result


def test_brief_does_not_publish_state_from_a_different_date():
    result = render_daily_brief("2026-11-03", "HISTORY", {
        "as_of_trade_date": "2026-11-04", "observed_state": "不应展示的状态",
    })
    assert "不应展示的状态" not in result
    assert "日期不一致" in result
