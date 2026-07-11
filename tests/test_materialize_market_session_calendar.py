from __future__ import annotations

import json
from pathlib import Path

from tools import materialize_market_session_calendar as tool


def _dates() -> list[str]:
    return ["2026-06-10", "2026-06-11", "2026-06-12"]


def test_build_provider_derived_reference_has_explicit_non_authoritative_scope():
    reference = tool.build_provider_derived_reference(_dates())
    assert reference["source_classification"] == "provider_derived"
    assert reference["coverage_start"] == "2026-06-10"
    assert reference["coverage_end"] == "2026-06-12"
    assert "not exchange-authoritative" in reference["calendar_semantics"]


def test_dry_run_does_not_write_output(tmp_path, monkeypatch):
    output = tmp_path / "market_session_calendar.json"
    monkeypatch.setattr(tool, "_load_akshare_sina_dates", _dates)
    rc = tool.main(["--dry-run", "--json", "--output", str(output)])
    assert rc == 0
    assert not output.exists()


def test_write_creates_only_requested_output(tmp_path, monkeypatch):
    output = tmp_path / "market_session_calendar.json"
    monkeypatch.setattr(tool, "_load_akshare_sina_dates", _dates)
    rc = tool.main(["--write", "--json", "--output", str(output)])
    assert rc == 0
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["eligible_session_dates"] == _dates()


def test_validate_only_reads_existing_reference_without_fetch(tmp_path, monkeypatch):
    output = tmp_path / "market_session_calendar.json"
    output.write_text(
        json.dumps(tool.build_provider_derived_reference(_dates()), ensure_ascii=False),
        encoding="utf-8",
    )

    def fail_fetch():
        raise AssertionError("validate-only should not fetch provider dates")

    monkeypatch.setattr(tool, "_load_akshare_sina_dates", fail_fetch)
    rc = tool.main(["--validate-only", "--json", "--output", str(output)])
    assert rc == 0


def test_validate_only_missing_reference_returns_failure(tmp_path):
    output = tmp_path / "missing.json"
    rc = tool.main(["--validate-only", "--json", "--output", str(output)])
    assert rc == 1
    assert not output.exists()


def test_main_summary_uses_counts_not_full_calendar_lists(tmp_path, monkeypatch, capsys):
    output = tmp_path / "market_session_calendar.json"
    monkeypatch.setattr(tool, "_load_akshare_sina_dates", _dates)
    rc = tool.main(["--dry-run", "--json", "--output", str(output)])
    captured = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert captured["eligible_dates_added_count"] == 3
    assert "eligible_dates_added" not in captured
    assert len(captured["eligible_dates_added_preview"]) == 3
    assert "eligible_dates" not in captured["validation"]
    assert captured["validation"]["eligible_date_count"] == 3
