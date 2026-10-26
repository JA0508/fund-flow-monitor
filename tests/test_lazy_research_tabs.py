import ast
from pathlib import Path


def test_brief_does_not_supply_default_for_existing_session_selection():
    tree = ast.parse(Path("app.py").read_text())
    guards = [node for node in ast.walk(tree) if isinstance(node, ast.If)
              and ast.unparse(node.test) == "'brief_provenance_theme' in st.session_state"]
    assert len(guards) == 1
    assert ast.unparse(guards[0].body[0]) == "brief_theme_index = None"


def test_static_research_does_not_schedule_refresh():
    tree = ast.parse(Path("app.py").read_text())
    guards = [n for n in ast.walk(tree) if isinstance(n, ast.If)
              and ast.unparse(n.test) == "not sample_mode and (not history_mode_requested)"]
    assert guards
    assert any(isinstance(n, ast.Call) and ast.unparse(n.func) == "st_autorefresh"
               for n in ast.walk(guards[0]))


def test_multi_day_work_runs_only_when_selected():
    tree = ast.parse(Path("app.py").read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    guards = [n for n in main.body if isinstance(n, ast.If)
              and ast.unparse(n.test) == "tab_multi_day.open"]
    assert len(guards) == 1
    assert isinstance(guards[0].body[0], ast.With)
    assert ast.unparse(guards[0].body[0].items[0].context_expr) == "tab_multi_day"
    tabs = next(n for n in ast.walk(main) if isinstance(n, ast.Call)
                and ast.unparse(n.func) == "st.tabs")
    assert any(k.arg == "on_change" and isinstance(k.value, ast.Name)
               and k.value.id == "_research_navigation_changed" for k in tabs.keywords)


def test_brief_extended_computation_is_opt_in():
    tree = ast.parse(Path("app.py").read_text())
    guards = [n for n in ast.walk(tree) if isinstance(n, ast.If)
              and ast.unparse(n.test) == "include_extended_brief"]
    assert len(guards) == 1
    calls = [ast.unparse(n.func) for n in ast.walk(guards[0]) if isinstance(n, ast.Call)]
    assert "compare_relationship_specifications" in calls
    assert "build_theme_observation_cube" in calls
    assert "扩展证据未运行" in ast.unparse(guards[0].orelse)
