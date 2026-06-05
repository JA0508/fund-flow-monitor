from __future__ import annotations

import pandas as pd

from src.theme_history_viz import (
    build_theme_history_visual_notes,
    build_theme_history_visual_summary,
    get_theme_history_chart_options,
    normalize_theme_history_chart_option,
    prepare_latest_theme_bar_data,
    prepare_status_timeline_compact,
    prepare_theme_history_heatmap_data,
    prepare_theme_history_line_data,
    validate_theme_history_viz_text,
)


def _theme_history_df() -> pd.DataFrame:
    rows = []
    themes = ["半导体/芯片链", "AI算力/TMT", "新能源链", "红利防御", "医药", "消费"]
    values = {
        "2026-01-15": [20, 30, -15, 10, -8, 3],
        "2026-01-16": [52, 112, -42, 13, -25, -11],
    }
    for data_date, amounts in values.items():
        for theme_name, amount in zip(themes, amounts, strict=True):
            rows.append(
                {
                    "source_type": "SAMPLE",
                    "data_date": data_date,
                    "captured_time": "14:50:00",
                    "theme_name": theme_name,
                    "theme_group": "测试分组",
                    "main_net_inflow_billion": amount,
                    "theme_status": "强流入" if amount > 30 else "强流出" if amount < -30 else "分歧/中性",
                    "source_count": 2,
                }
            )
    return pd.DataFrame(rows)


def _timeline_df() -> pd.DataFrame:
    df = _theme_history_df()
    df["status_change_label"] = ["样本不足", "延续偏强", "分化震荡", "延续承压", "由弱转强", "由强转弱"] * 2
    df["status_change_reason"] = "历史状态观察，不预测未来。"
    return df


def test_chart_options_and_normalize() -> None:
    options = get_theme_history_chart_options()
    assert len(options) == 4
    assert "主题净流入折线图" in options
    assert normalize_theme_history_chart_option(None) == "主题净流入折线图"
    assert normalize_theme_history_chart_option("未知") == "主题净流入折线图"
    assert normalize_theme_history_chart_option("主题历史热力矩阵") == "主题历史热力矩阵"


def test_prepare_line_data_empty_and_top_n() -> None:
    assert prepare_theme_history_line_data(pd.DataFrame()).empty
    line_df = prepare_theme_history_line_data(_theme_history_df(), top_n=3)
    assert not line_df.empty
    assert line_df["theme_name"].nunique() == 3


def test_prepare_line_data_top_n_cap() -> None:
    line_df = prepare_theme_history_line_data(_theme_history_df(), top_n=99)
    assert line_df["theme_name"].nunique() <= 10


def test_prepare_line_data_selected_themes() -> None:
    line_df = prepare_theme_history_line_data(_theme_history_df(), selected_themes=["医药"], top_n=5)
    assert line_df["theme_name"].unique().tolist() == ["医药"]


def test_prepare_heatmap_data_and_top_n_cap() -> None:
    heatmap_df = prepare_theme_history_heatmap_data(_theme_history_df(), top_n=4)
    assert "data_date" in heatmap_df.columns
    assert len(heatmap_df.columns) == 5
    capped_df = prepare_theme_history_heatmap_data(_theme_history_df(), top_n=99)
    assert len(capped_df.columns) <= 13


def test_prepare_latest_bar_data_and_top_n_cap() -> None:
    bar_df = prepare_latest_theme_bar_data(_theme_history_df(), top_n=4)
    assert len(bar_df) == 4
    assert bar_df["data_date"].nunique() == 1
    assert bar_df["data_date"].iloc[0] == "2026-01-16"
    capped_df = prepare_latest_theme_bar_data(_theme_history_df(), top_n=99)
    assert len(capped_df) <= 20


def test_prepare_status_timeline_compact_limits_rows() -> None:
    compact_df = prepare_status_timeline_compact(_timeline_df(), max_rows=5)
    assert len(compact_df) == 5
    capped_df = prepare_status_timeline_compact(pd.concat([_timeline_df()] * 30, ignore_index=True), max_rows=999)
    assert len(capped_df) <= 200


def test_visual_summary_empty() -> None:
    summary = build_theme_history_visual_summary(pd.DataFrame())
    assert summary["visual_available"] is False
    assert summary["visual_summary_label"] == "暂无可视化数据"


def test_visual_summary_sample_data() -> None:
    summary = build_theme_history_visual_summary(_theme_history_df(), _timeline_df(), top_n=5)
    assert summary["visual_available"] is True
    assert summary["visual_summary_label"] == "仅 SAMPLE 图表可用"
    assert "SAMPLE 合成演示数据" in summary["visual_summary_reason"]
    assert summary["line_theme_count"] <= 5


def test_visual_notes_sample_only() -> None:
    notes = build_theme_history_visual_notes("SAMPLE", "代表口径", True, is_sample_only=True)
    joined = "\n".join(notes)
    assert "合成演示数据" in joined
    assert "不代表真实行情" in joined
    assert "不预测未来走势" in joined


def test_validate_theme_history_viz_text_detects_forbidden_words() -> None:
    hits = validate_theme_history_viz_text("这里写了趋势确立和明确机会")
    assert "趋势确立" in hits
    assert "明确机会" in hits


def test_normal_visual_notes_have_no_forbidden_words() -> None:
    notes = build_theme_history_visual_notes("SAMPLE", "代表口径", True, is_sample_only=True)
    assert validate_theme_history_viz_text("\n".join(notes)) == []
