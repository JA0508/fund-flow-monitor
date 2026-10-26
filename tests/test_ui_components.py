from __future__ import annotations

from src import ui_components


def test_render_status_bar_groups_all_status_context_for_narrow_screens(monkeypatch):
    rendered_html: list[str] = []
    monkeypatch.setattr(
        ui_components.st,
        "markdown",
        lambda html, unsafe_allow_html=False: rendered_html.append(html),
    )

    ui_components.render_status_bar(
        market_status="closed",
        refresh_interval=30,
        data_status="SAMPLE",
        status_note="合成样例，不代表真实行情。",
        sector_type="行业资金流",
        latest_label="样例时间",
        latest_time="14:50:00",
        extra_text="主题口径：严格代表口径",
        selected_snapshot_date="2026-01-16",
        captured_time_count=5,
        quality_label="快照可回放",
        data_source_label="SAMPLE synthetic CSV",
    )

    status_html = rendered_html[0]
    assert status_html.count("status-group") == 4
    assert "数据源：<b>SAMPLE synthetic CSV</b>" in status_html
    assert "数据状态：<span class='status-sample'>SAMPLE</span>" in status_html
    assert "状态说明：<b>合成样例，不代表真实行情。</b>" in status_html
    assert "数据日期：<b>2026-01-16</b>" in status_html
    assert "时间点：<b>5</b>" in status_html
    assert "质量：<b>快照可回放</b>" in status_html
    assert "主题口径：严格代表口径" in status_html
