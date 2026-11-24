import ast
from pathlib import Path


def test_brief_history_calls_have_cutoffs():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())
    expected = {
        "brief_dynamics_cube": "as_of_trade_date",
        "brief_relationship_robustness": "as_of_trade_date",
        "brief_sector_history": "end_date",
        "brief_daily_theme_df": "as_of_trade_date",
    }
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in expected:
                assert expected[target.id] in {kw.arg for kw in node.value.keywords}
                found.add(target.id)
    assert found == set(expected)


def test_warehouse_brief_does_not_fallback_to_other_source():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())
    assignments = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "brief_history_source" for t in node.targets)
    ]
    assert len(assignments) == 1
    value = assignments[0]
    assert isinstance(value, ast.IfExp)
    assert value.body.value == "SAMPLE"
    assert value.orelse.value == "LOCAL"
