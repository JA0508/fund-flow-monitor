import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest


def _helpers():
    tree = ast.parse(Path("app.py").read_text())
    names = {"_research_navigation_changed", "_prepare_research_navigation"}
    return "\n".join(ast.unparse(n) for n in tree.body
                     if isinstance(n, ast.FunctionDef) and n.name in names)


def test_navigation_does_not_acquire_and_preserves_hidden_filters():
    app = AppTest.from_string(
        "import streamlit as st\n" + _helpers() + "\n"
        "navigation_only = _prepare_research_navigation()\n"
        "if not navigation_only:\n"
        "    st.session_state['fetch_count'] = st.session_state.get('fetch_count', 0) + 1\n"
        "    st.session_state['write_count'] = st.session_state.get('write_count', 0) + 1\n"
        "show = st.checkbox('Show research', value=True, on_change=_research_navigation_changed)\n"
        "if show:\n"
        "    st.selectbox('Source', ['ALL', 'LOCAL'], key='theme_history_source_type')\n"
        "    st.selectbox('Theme', ['A', 'B'], key='multi_day_evidence_theme')\n"
    ).run()
    assert not app.exception
    app.selectbox[0].select('LOCAL').run()
    app.selectbox[1].select('B').run()
    before = (app.session_state['fetch_count'], app.session_state['write_count'])
    app.checkbox[0].uncheck().run()
    app.checkbox[0].check().run()
    assert not app.exception
    assert (app.session_state['fetch_count'], app.session_state['write_count']) == before
    assert app.selectbox[0].value == 'LOCAL'
    assert app.selectbox[1].value == 'B'


def test_navigation_guard_is_wired_before_all_fetch_paths():
    tree = ast.parse(Path('app.py').read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    source = ast.unparse(main)
    assert 'navigation_only = _prepare_research_navigation()' in source
    assert 'can_fetch = market_status in FETCH_ALLOWED_STATUSES' in source
    assert 'should_fetch = can_fetch and (not navigation_only)' in source
    assert 'if should_fetch and (not is_concept_main):' in source
    assert 'and should_fetch and' in source
    tabs = next(n for n in ast.walk(main) if isinstance(n, ast.Call) and ast.unparse(n.func) == 'st.tabs')
    assert any(k.arg == 'on_change' and ast.unparse(k.value) == '_research_navigation_changed' for k in tabs.keywords)
