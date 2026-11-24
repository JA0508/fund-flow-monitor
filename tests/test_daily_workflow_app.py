from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_public_demo_rejects_stale_real_source_selection(monkeypatch):
    monkeypatch.setenv("FUND_FLOW_PUBLIC_DEMO", "1")
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=120)
    app.session_state["data_source_mode"] = "真实数据 / 本地缓存"
    app.run()
    assert not app.exception
    assert app.selectbox(key="data_source_mode").options == ["演示样例数据"]
    assert app.session_state["data_source_mode"] == "演示样例数据"


def test_calendar_opens_selected_sample_brief_and_rejects_missing_date(monkeypatch):
    monkeypatch.setenv("FUND_FLOW_PUBLIC_DEMO", "1")
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=120).run()
    assert not app.exception
    assert not any("真实缓存日期" in item.value for item in app.text)
    assert any(item.label == "核心与广度对照" for item in app.expander)
    selected = app.session_state["selected_sample_snapshot_date"]
    app.button(key="open_calendar_brief").click().run()
    assert not app.exception
    assert app.session_state["daily_navigation"] == "我的关注"
    assert app.session_state["selected_sample_snapshot_date"] == selected
    app.date_input(key="observation_calendar_day").set_value(date(2026, 2, 1)).run()
    assert not app.exception
    assert not any(button.key == "open_calendar_brief" for button in app.button)
    assert any("当天没有可用缓存" in item.value for item in app.info)
    app.button(key="open_latest_calendar_brief").click().run()
    assert not app.exception
    assert app.session_state["daily_navigation"] == "我的关注"
    assert app.session_state["selected_sample_snapshot_date"] == selected
