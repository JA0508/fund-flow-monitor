import json

import pandas as pd

from src.watchlist import filter_watchlist_theme_df, get_watchlist_themes, load_watchlist


def test_missing_config_returns_default(tmp_path):
    watchlist = load_watchlist(str(tmp_path / "missing.json"))
    assert watchlist["watchlist_name"] == "默认关注主题"
    assert "半导体/芯片链" in watchlist["themes"]


def test_can_read_config_watchlist(tmp_path):
    path = tmp_path / "watchlist.json"
    path.write_text(json.dumps({"watchlist_name": "test", "themes": ["A", "B"]}), encoding="utf-8")
    watchlist = load_watchlist(str(path))
    assert watchlist["watchlist_name"] == "test"
    assert get_watchlist_themes(watchlist) == ["A", "B"]


def test_fallback_watchlists_do_not_share_mutable_themes(tmp_path):
    first = load_watchlist(str(tmp_path / "missing.json"))
    first["themes"].clear()
    assert load_watchlist(str(tmp_path / "missing.json"))["themes"]


def test_invalid_config_reports_fallback_without_private_details(tmp_path):
    path = tmp_path / "private.json"
    for content in ('{broken', '[]', '{"themes": "private-secret"}', '{"themes": [null]}'):
        path.write_text(content, encoding="utf-8")
        result = load_watchlist(str(path))
        assert result.get("_load_warning")
        assert "private-secret" not in result["_load_warning"]
        assert str(path) not in result["_load_warning"]


def test_explicit_empty_watchlist_is_not_replaced(tmp_path):
    path = tmp_path / "watchlist.json"
    path.write_text('{"themes": []}', encoding="utf-8")
    assert load_watchlist(str(path))["themes"] == []


def test_filter_watchlist_theme_df_ignores_missing_theme():
    df = pd.DataFrame({"theme_name": ["A", "B"], "main_net_inflow_billion": [1, 2]})
    filtered = filter_watchlist_theme_df(df, ["B", "C"])
    assert filtered["theme_name"].tolist() == ["B"]

