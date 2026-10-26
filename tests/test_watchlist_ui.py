import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize(
    ("content", "warning_expected"),
    [("{broken", True), ('{"themes": ["A"]}', False), ('{"themes": []}', False)],
)
def test_home_watchlist_warning_renders_without_loading_market_data(tmp_path, content, warning_expected):
    path = tmp_path / "watchlist.json"
    path.write_text(content, encoding="utf-8")
    tree = ast.parse(Path("app.py").read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    guards = [
        node for node in main.body
        if isinstance(node, ast.If)
        and ast.unparse(node.test) == "watchlist.get('_load_warning')"
    ]
    assert len(guards) == 1
    # Execute the actual UI guard, excluding startup that reads local market caches.
    script = (
        "import streamlit as st\n"
        "from src.watchlist import load_watchlist\n"
        f"watchlist = load_watchlist({str(path)!r})\n"
        + ast.unparse(guards[0])
    )
    app = AppTest.from_string(script).run()
    assert not app.exception
    assert len(app.warning) == int(warning_expected)
    if warning_expected:
        assert "并非已恢复个人选择" in app.warning[0].value
        assert str(path) not in app.warning[0].value
