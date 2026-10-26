import pytest
import pandas as pd

from src.watchlist import (
    filter_watchlist_theme_df,
    get_watchlist_themes,
    load_watchlist,
    save_personal_watchlist,
)
from src.theme_observation_evidence import get_theme_observation_theme_options


@pytest.mark.parametrize("selected, expected", [(["B"], ["B", "A"]), ([], ["A", "B"])])
def test_restored_watchlist_prioritizes_brief_options(tmp_path, selected, expected):
    path = tmp_path / "watchlist.json"
    radar = pd.DataFrame({"theme_name": ["A", "B"]})
    original = radar.copy(deep=True)
    save_personal_watchlist(path, selected, ["A", "B"])
    restored = get_watchlist_themes(load_watchlist(str(path)))
    watched = filter_watchlist_theme_df(radar, restored)
    assert restored == selected
    assert get_theme_observation_theme_options(watched, radar) == expected
    pd.testing.assert_frame_equal(radar, original)


def test_save_reload_and_clear(tmp_path):
    path = tmp_path / "preferences" / "watchlist.json"
    save_personal_watchlist(path, ["A", "B", "A"], ["A", "B"])
    assert load_watchlist(str(path))["themes"] == ["A", "B"]
    save_personal_watchlist(path, [], ["A", "B"])
    assert load_watchlist(str(path))["themes"] == []


@pytest.mark.parametrize("themes", [["unknown"], [None], "A"])
def test_invalid_selection_does_not_replace_file(tmp_path, themes):
    path = tmp_path / "watchlist.json"
    path.write_text("original", encoding="utf-8")
    with pytest.raises(ValueError):
        save_personal_watchlist(path, themes, ["A"])
    assert path.read_text() == "original"


def test_failed_replace_preserves_previous_selection(tmp_path, monkeypatch):
    import src.watchlist as module
    path = tmp_path / "watchlist.json"
    path.write_text("original", encoding="utf-8")
    def fail(*args):
        raise OSError("private path")
    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError):
        save_personal_watchlist(path, ["A"], ["A"])
    assert path.read_text() == "original"
    assert list(tmp_path.iterdir()) == [path]
