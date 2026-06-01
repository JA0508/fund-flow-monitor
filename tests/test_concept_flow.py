import pandas as pd

from src.concept_flow import (
    get_concept_cache_summary,
    get_concept_latest_snapshot,
    should_refresh_concept_cache,
    summarize_concept_hotspots,
)


def _row(name, value, captured_time, sector_type="概念资金流"):
    return {
        "captured_at": f"2026-06-01 {captured_time}",
        "captured_time": captured_time,
        "sector_type": sector_type,
        "sector_name": name,
        "main_net_inflow_billion": value,
        "change_pct": 1.2,
        "main_net_ratio": 3.4,
        "leading_stock": f"{name}龙头",
    }


def test_get_concept_latest_snapshot_uses_latest_captured_at():
    df = pd.DataFrame(
        [
            _row("人工智能", 1, "10:00:00"),
            _row("锂电池", 2, "10:05:00"),
            _row("行业A", 3, "10:10:00", sector_type="行业资金流"),
        ]
    )
    latest = get_concept_latest_snapshot(df)
    assert latest["sector_name"].tolist() == ["锂电池"]


def test_get_concept_cache_summary_counts_rows_and_times():
    df = pd.DataFrame([_row("人工智能", 1, "10:00:00"), _row("锂电池", 2, "10:05:00")])
    summary = get_concept_cache_summary(df)
    assert summary["has_concept_cache"] is True
    assert summary["concept_rows"] == 2
    assert summary["concept_unique_times"] == 2
    assert summary["latest_concept_time"] == "10:05:00"


def test_should_refresh_concept_cache_handles_empty_expired_and_fresh():
    now = pd.Timestamp("2026-06-01 10:10:00")
    assert should_refresh_concept_cache(None, now) is True
    assert should_refresh_concept_cache(pd.Timestamp("2026-06-01 10:00:00"), now, 5) is True
    assert should_refresh_concept_cache(pd.Timestamp("2026-06-01 10:08:00"), now, 5) is False


def test_summarize_concept_hotspots_adds_status():
    df = pd.DataFrame(
        [
            _row("人工智能", 25, "10:00:00"),
            _row("锂电池", 8, "10:00:00"),
            _row("光刻机", -30, "10:00:00"),
        ]
    )
    hotspots = summarize_concept_hotspots(df, top_n=3)
    assert "hotspot_status" in hotspots.columns
    assert set(hotspots["hotspot_status"]) == {"强流入概念", "流入概念", "强流出概念"}
