import pandas as pd
import pytest

from src import theme_dynamics as dynamics
from src import analytical_robustness as robustness


def test_cube_cutoff_filters_inputs_before_limit_and_manifest(monkeypatch):
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    monkeypatch.setattr(dynamics, "_load_catalog", lambda *a: pd.DataFrame({"snapshot_date": dates}))
    monkeypatch.setattr(dynamics, "build_snapshot_manifest", lambda **k: pd.DataFrame({"trade_date": dates, "captured_time": ["15:00"] * 3}))
    loaded = []

    def load(*args):
        loaded.append(args[1])
        return pd.DataFrame()

    monkeypatch.setattr(dynamics, "_load_snapshot", load)
    cube = dynamics.build_theme_observation_cube(taxonomy={"test": True}, limit_dates=1, as_of_trade_date="2026-01-02")
    assert loaded == ["2026-01-02"]
    assert cube.attrs["manifest"]["trade_date"].tolist() == dates[:2]


def test_relationship_cutoff_reaches_cube_and_lineage(monkeypatch):
    seen = []
    monkeypatch.setattr(robustness, "build_canonical_cube_for_spec", lambda *a, **k: seen.append(k.get("as_of_trade_date")) or pd.DataFrame())
    monkeypatch.setattr(robustness, "summarize_relationship_variant", lambda *a: {})
    monkeypatch.setattr(robustness, "build_snapshot_manifest", lambda *a, **k: pd.DataFrame({"trade_date": ["2026-01-01", "2026-01-03"]}))
    monkeypatch.setattr(robustness, "build_provider_lineage_summary", lambda df: seen.append(df["trade_date"].tolist()) or {})
    robustness.compare_relationship_specifications("a", "b", bucket_minutes=[5], as_of_trade_date="2026-01-02")
    assert seen == ["2026-01-02", ["2026-01-01"]]


def test_invalid_cutoff_rejected():
    with pytest.raises(ValueError):
        dynamics.build_theme_observation_events(as_of_trade_date="not-a-date")


def test_cutoff_rejects_snapshot_without_verifiable_row_dates(monkeypatch):
    monkeypatch.setattr(dynamics, "_load_catalog", lambda *a: pd.DataFrame({"snapshot_date": ["2026-01-02"]}))
    monkeypatch.setattr(dynamics, "build_snapshot_manifest", lambda **k: pd.DataFrame())
    monkeypatch.setattr(dynamics, "_load_snapshot", lambda *a: pd.DataFrame({"sector_name": ["test"]}))
    frames = []
    monkeypatch.setattr(dynamics, "_industry_frame", lambda df: frames.append(df) or pd.DataFrame())
    events = dynamics.build_theme_observation_events(taxonomy={"test": True}, as_of_trade_date="2026-01-02")
    assert not frames or all(frame.empty for frame in frames)
    assert any("日期" in warning for warning in events.attrs["warnings"])
