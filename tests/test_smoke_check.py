from pathlib import Path

import pandas as pd

from tools.smoke_check import (
    check_project_files,
    check_python_version,
    load_watchlist_status,
    summarize_csv,
)


def test_check_python_version_passes_current_runtime():
    result = check_python_version()
    assert result["ok"] is True
    assert result["required"] == "3.10+"


def test_check_project_files_reports_missing_files(tmp_path):
    (tmp_path / "app.py").write_text("", encoding="utf-8")
    result = check_project_files(tmp_path)
    assert result["app.py"] is True
    assert result["src/theme_pool.py"] is False
    assert result[".streamlit/config.toml"] is False


def test_load_watchlist_status_reads_custom_file(tmp_path):
    path = tmp_path / "watchlist.json"
    path.write_text('{"watchlist_name":"测试关注","themes":["半导体/芯片链"]}', encoding="utf-8")
    status = load_watchlist_status(path)
    assert status["ok"] is True
    assert status["watchlist_name"] == "测试关注"
    assert status["themes"] == ["半导体/芯片链"]


def test_summarize_csv_reports_rows_and_latest_time(tmp_path):
    path = tmp_path / "sector_flow_2026-06-01.csv"
    pd.DataFrame({"captured_time": ["10:00:00", "10:05:00", "10:05:00"]}).to_csv(path, index=False)
    summary = summarize_csv(Path(path))
    assert summary["exists"] is True
    assert summary["rows"] == 3
    assert summary["captured_time_count"] == 2
    assert summary["latest_captured_time"] == "10:05:00"


def test_summarize_csv_handles_missing_file():
    summary = summarize_csv(None)
    assert summary["exists"] is False
    assert summary["rows"] == 0
