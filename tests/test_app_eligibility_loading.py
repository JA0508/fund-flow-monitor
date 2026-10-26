import ast
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock

import pytest


def load_renderer(clicked=False):
    tree = ast.parse(Path("app.py").read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "_render_requested_eligibility"]
    assert functions, "Eligibility analysis must be explicitly requested, not run at startup"
    st = Mock()
    st.button.return_value = clicked
    st.spinner.return_value = nullcontext()
    namespace = {
        "st": st,
        "build_theme_observation_cube": Mock(return_value="cube"),
        "build_availability_vs_qualified_readiness": Mock(return_value="report"),
        "render_analytical_eligibility_summary_cards": Mock(),
        "WORKLOAD_THEME_CONTINUITY": "continuity",
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


def test_unrequested_analysis_does_not_load_or_claim_qualification():
    ns = load_renderer()
    ns["_render_requested_eligibility"]("REAL", "unused", {}, "REAL audit")
    ns["build_theme_observation_cube"].assert_not_called()
    ns["render_analytical_eligibility_summary_cards"].assert_not_called()
    assert "未运行" in ns["st"].caption.call_args.args[0]


@pytest.mark.parametrize("source", ["REAL", "SAMPLE"])
def test_requested_analysis_uses_only_its_source(source):
    ns = load_renderer(clicked=True)
    ns["_render_requested_eligibility"](source, "fixture-dir", {"readable": True}, "audit")
    ns["build_theme_observation_cube"].assert_called_once_with(source_mode=source, data_dir="fixture-dir")
    ns["build_availability_vs_qualified_readiness"].assert_called_once_with(
        {"readable": True}, "cube", workload="continuity")
    ns["render_analytical_eligibility_summary_cards"].assert_called_once_with("report", title="audit")


def test_failed_analysis_is_not_rendered_as_empty_or_qualified():
    ns = load_renderer(clicked=True)
    ns["build_theme_observation_cube"].side_effect = ValueError("private details")
    ns["_render_requested_eligibility"]("REAL", "unused", {}, "audit")
    ns["render_analytical_eligibility_summary_cards"].assert_not_called()
    ns["st"].error.assert_called_once()
    assert "private details" not in ns["st"].error.call_args.args[0]


def test_startup_has_no_unconditional_eligibility_cubes():
    tree = ast.parse(Path("app.py").read_text())
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    for statement in main.body:
        if isinstance(statement, ast.With):
            break
        calls = [node for node in ast.walk(statement) if isinstance(node, ast.Call)]
        assert not any(isinstance(call.func, ast.Name) and call.func.id == "build_theme_observation_cube"
                       for call in calls)
