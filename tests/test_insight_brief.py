import pandas as pd

from src.insight_brief import (
    build_data_context_summary,
    build_observation_brief,
    render_brief_markdown,
    summarize_holding_pool_for_brief,
    summarize_intraday_for_brief,
    summarize_multi_day_for_brief,
    summarize_taxonomy_coverage_for_brief,
    summarize_theme_radar_for_brief,
    validate_brief_text,
)


FORBIDDEN = ["买入", "卖出", "加仓", "减仓", "抄底", "逃顶", "推荐买", "建议买", "建仓", "清仓", "未来会涨", "未来会跌"]


def test_build_data_context_summary_status_labels():
    summary = {"captured_time_count": 3, "latest_captured_time": "10:30:00"}
    assert build_data_context_summary("2026-06-03", "LIVE", summary, "严格代表口径")["data_context_label"] == "实时观察"
    assert build_data_context_summary("2026-06-03", "CACHE", summary, "严格代表口径")["data_context_label"] == "缓存观察"
    assert build_data_context_summary("2026-06-01", "HISTORY", summary, "严格代表口径")["data_context_label"] == "历史回放"
    assert build_data_context_summary("2026-06-03", "DEMO", summary, "严格代表口径")["data_context_label"] == "模拟演示"
    sample = build_data_context_summary("2026-01-16", "SAMPLE", summary, "严格代表口径")
    assert sample["data_context_label"] == "演示样例"
    assert "不代表真实行情" in sample["data_context_reason"]
    assert build_data_context_summary("2026-06-03", "EMPTY", {}, "严格代表口径")["data_context_label"] == "暂无真实数据"


def test_summarize_theme_radar_for_brief_labels():
    strong = pd.DataFrame(
        {
            "theme_name": ["A", "B", "C"],
            "theme_status": ["强流入", "弱流入", "分歧/中性"],
            "main_net_inflow_billion": [40, 10, 0],
        }
    )
    cold = pd.DataFrame(
        {
            "theme_name": ["A", "B", "C"],
            "theme_status": ["强流出", "弱流出", "分歧/中性"],
            "main_net_inflow_billion": [-40, -10, 0],
        }
    )
    mixed = pd.DataFrame(
        {
            "theme_name": ["A", "B"],
            "theme_status": ["强流入", "强流出"],
            "main_net_inflow_billion": [40, -40],
        }
    )
    assert summarize_theme_radar_for_brief(strong)["radar_summary_label"] == "主题资金偏强"
    assert summarize_theme_radar_for_brief(cold)["radar_summary_label"] == "主题资金偏冷"
    assert summarize_theme_radar_for_brief(mixed)["radar_summary_label"] == "主题资金分化"


def test_intraday_and_multi_day_sample_shortage_are_readable():
    intraday = summarize_intraday_for_brief({}, pd.DataFrame())
    multi_day = summarize_multi_day_for_brief({"date_count": 1}, pd.DataFrame({"theme_name": ["A"]}))
    assert intraday["intraday_available"] is False
    assert "样本不足" in intraday["intraday_summary_label"]
    assert multi_day["multi_day_available"] is False
    assert "缓存日期不足" in multi_day["multi_day_summary_reason"]


def test_holding_pool_summary_has_no_fund_prediction_wording():
    df = pd.DataFrame(
        {
            "fund_name": ["A基金", "B基金"],
            "weighted_impact_score": [1.2, -1.1],
        }
    )
    summary = summarize_holding_pool_for_brief(df)
    text = summary["holding_summary_reason"] + " ".join(summary["strongest_funds"]) + " ".join(summary["pressured_funds"])
    assert "净值" not in text
    for word in FORBIDDEN:
        assert word not in text


def test_coverage_summary_explains_low_ratio():
    coverage = {
        "coverage_label": "主题覆盖偏低",
        "coverage_ratio": 0.15,
        "coverage_reason": "当前主题库覆盖偏低。",
        "high_flow_uncovered_df": pd.DataFrame({"sector_name": ["未覆盖"]}),
        "duplicated_sector_df": pd.DataFrame({"sector_name": ["银行"]}),
    }
    summary = summarize_taxonomy_coverage_for_brief(coverage, {"consistency_label": "全部一致"})
    assert summary["coverage_available"] is True
    assert "覆盖率偏低不代表数据异常" in summary["coverage_summary_reason"]


def test_build_observation_brief_and_markdown_are_valid():
    data_context = build_data_context_summary(
        "2026-06-03",
        "HISTORY",
        {"captured_time_count": 12, "latest_captured_time": "14:30:00"},
        "严格代表口径",
    )
    radar = summarize_theme_radar_for_brief(
        pd.DataFrame(
            {
                "theme_name": ["半导体/芯片链", "新能源链"],
                "theme_status": ["强流入", "强流出"],
                "main_net_inflow_billion": [50, -40],
            }
        )
    )
    intraday = summarize_intraday_for_brief(
        {"summary_label": "日内热点分化", "summary_reason": "当前日内主题资金结构分化。"},
        pd.DataFrame({"theme_name": ["半导体/芯片链"], "hotspot_type": ["persistent_inflow"], "latest_value": [50], "abs_value_change": [20]}),
    )
    multi_day = summarize_multi_day_for_brief(
        {"date_count": 2, "summary_label": "多日主题结构分化", "summary_reason": "当前多个缓存日期中的主题资金状态分化。"},
        pd.DataFrame({"theme_name": ["半导体/芯片链"], "trend_type": ["persistent_strength"], "latest_value": [50], "abs_value_change": [80]}),
    )
    holding = summarize_holding_pool_for_brief(pd.DataFrame({"fund_name": ["A基金"], "weighted_impact_score": [0.4]}))
    coverage = summarize_taxonomy_coverage_for_brief({"coverage_label": "主题覆盖中等", "coverage_ratio": 0.5}, {"consistency_label": "全部一致"})
    brief = build_observation_brief(data_context, radar, intraday, multi_day, holding, coverage)
    markdown = render_brief_markdown(brief)
    assert brief["executive_summary"]
    assert len(brief["key_points"]) >= 3
    assert "## 一、摘要" in markdown
    assert "## 四、免责声明" in markdown
    assert validate_brief_text(markdown) == []


def test_validate_brief_text_detects_forbidden_words():
    hits = validate_brief_text("这里出现建议买和未来会涨。")
    assert "建议买" in hits
    assert "未来会涨" in hits
