from streamlit.testing.v1 import AppTest


def test_daily_entry_exposes_missing_evidence_without_claiming_ready():
    app = AppTest.from_string('''
from src.daily_status_ui import render_daily_status
render_daily_status("SAMPLE", {"staleness_status": "today", "latest_snapshot_date": "2026-10-22"}, {"latest_run_status": "fetch_error"})
''').run()
    assert not app.exception
    assert "SAMPLE" in app.info[0].value
    assert "不代表" in app.info[0].value
    text = "\n".join(item.value for item in app.text)
    assert "2026-10-22" in text
    assert "fetch_error" in text
    assert "未提供" in text
    assert "不证明" in app.caption[0].value


def test_daily_entry_shows_future_cache_and_capture_source():
    app = AppTest.from_string('''
from src.daily_status_ui import render_daily_status
render_daily_status("CACHE", {"staleness_status": "future", "latest_captured_time": "14:50", "latest_source": "provider", "quality_label": "warning"}, {})
''').run()
    assert not app.exception
    text = "\n".join(item.value for item in app.text)
    assert "未来日期" in text
    assert "14:50" in text
    assert "provider" in text
    assert "warning" in text
    assert "无运行记录" in text


def test_outside_calendar_coverage_is_visible():
    app = AppTest.from_string('''
from src.daily_status_ui import render_daily_status
render_daily_status("CACHE", {"latest_snapshot_date": "2999-01-01"}, {})
''').run()
    assert not app.exception
    text = "\n".join(item.value for item in app.text)
    assert "market_calendar_unverified" in text
    assert "日历覆盖范围" in text
    assert "outside" in text.lower()
    assert "非交易所权威" in "\n".join(item.value for item in app.caption)


def test_quality_reason_is_visible_without_raw_collector_error():
    app = AppTest.from_string('''
from src.daily_status_ui import render_daily_status
render_daily_status("CACHE", {"quality_reason": "只有一个时间点，无法判断完整日内变化。"}, {"latest_run_status": "fetch_error", "latest_message": "secret connection details"})
''').run()
    assert not app.exception
    text = "\n".join(item.value for item in app.text)
    assert "只有一个时间点" in text
    assert "secret connection" not in text


def test_broken_audit_is_not_reported_as_no_runs():
    app = AppTest.from_string('''
from src.daily_status_ui import render_daily_status
render_daily_status("CACHE", {}, {"log_exists": True, "warning_count": 1, "warnings": ["private path"]})
''').run()
    assert not app.exception
    text = "\n".join(item.value for item in app.text)
    assert "采集记录不可验证" in text
    assert "无运行记录" not in text
    assert "private path" not in text
