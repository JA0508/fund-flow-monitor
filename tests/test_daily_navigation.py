import ast
from pathlib import Path


def test_sidebar_adapts_to_small_devices():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())
    config = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == "set_page_config")
    assert next(ast.literal_eval(kw.value) for kw in config.keywords
                if kw.arg == "initial_sidebar_state") == "auto"


def test_daily_navigation_has_only_three_primary_destinations():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())
    primary = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Tuple) and
                       [getattr(item, "id", "") for item in target.elts] == ["today_tab", "watch_tab", "calendar_tab"]
                       for target in node.targets)]
    assert len(primary) == 1
    assert ast.literal_eval(primary[0].value.args[0]) == ("今日", "我的关注", "观察日历")


def test_tuning_controls_are_in_advanced_settings():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())
    labels = {"数据展示模式", "主题口径", "板块类型", "刷新间隔", "净流入 Top N", "净流出 Top N"}
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and node.args and isinstance(node.args[0], ast.Constant)
             and node.args[0].value in labels]
    assert len(calls) == len(labels)
    assert all(isinstance(call.func, ast.Attribute) and
               isinstance(call.func.value, ast.Name) and
               call.func.value.id == "advanced_settings" for call in calls)


def test_taxonomy_diagnostics_live_in_data_details():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())
    containers = [node for node in ast.walk(tree) if isinstance(node, ast.With)
                  and any(isinstance(item.context_expr, ast.Name) and
                          item.context_expr.id == "tab_data" for item in node.items)]
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == "render_theme_taxonomy_status"
               for container in containers for node in ast.walk(container))
