from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.intraday_hotspots import (
    build_intraday_hotspot_pool,
    build_theme_intraday_history,
    calculate_intraday_theme_metrics,
)
from src.insight_brief import build_data_context_summary, validate_brief_text
from src.multi_day_trends import (
    build_daily_theme_snapshots,
    build_multi_day_trend_pool,
    calculate_multi_day_theme_metrics,
)
from src.sample_data import (
    build_sample_snapshot_catalog,
    list_sample_snapshot_files,
    load_sample_snapshot_by_date,
    mark_sample_dataframe,
)
from src.snapshot_catalog import infer_view_data_status
from src.theme_pool import build_theme_snapshot
from src.theme_radar import build_theme_radar_snapshot
from tools.generate_sample_data import generate_sample_files


def _latest_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["captured_at"] = pd.to_datetime(work["captured_at"], errors="coerce")
    return work[work["captured_at"].eq(work["captured_at"].max())]


def test_sample_catalog_and_loading(tmp_path: Path) -> None:
    generate_sample_files(tmp_path)

    files = list_sample_snapshot_files(str(tmp_path))
    assert len(files) == 2
    assert files[0].name == "sector_flow_2026-01-16.csv"

    catalog = build_sample_snapshot_catalog(str(tmp_path))
    assert len(catalog) == 2
    assert catalog["is_sample"].all()
    assert catalog["captured_time_count"].min() >= 5

    df = load_sample_snapshot_by_date("2026-01-16", str(tmp_path))
    assert not df.empty
    assert df["source"].eq("SAMPLE").all()
    assert df["data_mode"].eq("SAMPLE").all()


def test_mark_sample_dataframe_adds_sample_marker() -> None:
    df = pd.DataFrame({"source": ["AKShare / Eastmoney"], "sector_name": ["半导体"]})
    marked = mark_sample_dataframe(df)
    assert marked["source"].iloc[0] == "SAMPLE"
    assert marked["data_mode"].iloc[0] == "SAMPLE"


def test_sample_data_builds_theme_radar_intraday_and_multiday(tmp_path: Path) -> None:
    generate_sample_files(tmp_path)
    catalog = build_sample_snapshot_catalog(str(tmp_path))
    ticks = load_sample_snapshot_by_date("2026-01-16", str(tmp_path))

    radar = build_theme_radar_snapshot(build_theme_snapshot(_latest_snapshot(ticks), "strict_representative"))
    assert not radar.empty
    assert "半导体/芯片链" in set(radar["theme_name"])

    history = build_theme_intraday_history(ticks, mode="breadth")
    metrics = calculate_intraday_theme_metrics(history)
    hotspots = build_intraday_hotspot_pool(metrics)
    assert not history.empty
    assert not hotspots.empty

    daily = build_daily_theme_snapshots(catalog, data_dir=str(tmp_path), mode="strict_representative")
    multi_metrics = calculate_multi_day_theme_metrics(daily)
    trend_pool = build_multi_day_trend_pool(multi_metrics)
    assert daily["snapshot_date"].nunique() == 2
    assert not trend_pool.empty


def test_sample_state_is_not_live_cache_or_history() -> None:
    assert infer_view_data_status("2026-01-16", "2026-06-04", "CACHE", False, is_sample=True) == "SAMPLE"


def test_sample_data_does_not_write_real_ticks(tmp_path: Path) -> None:
    sample_dir = tmp_path / "sample_data/ticks"
    real_dir = tmp_path / "data/ticks"
    generate_sample_files(sample_dir)
    _ = load_sample_snapshot_by_date("2026-01-15", str(sample_dir))
    assert not real_dir.exists()


def test_sample_context_text_has_no_actionable_forbidden_words() -> None:
    context = build_data_context_summary(
        "2026-01-16",
        "SAMPLE",
        {"captured_time_count": 5, "latest_captured_time": "14:50:00"},
        "严格代表口径",
    )
    assert context["data_context_label"] == "演示样例"
    assert validate_brief_text(context["data_context_reason"]) == []
