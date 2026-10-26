import ast
from pathlib import Path


def test_cache_summary_is_built_after_snapshot_writes_before_render():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    def lines(name):
        return [node.lineno for node in calls if isinstance(node.func, ast.Name) and node.func.id == name]
    writes = lines("append_snapshot")
    assert writes
    summary = lines("build_real_cache_summary")
    assert len(summary) == 1
    assert max(writes) < summary[0] < lines("render_daily_status")[0]
