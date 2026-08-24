from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import tools.import_real_snapshot as importer
from src.provider_contracts import PRIMARY_PROVIDER_ID, build_provider_contract_short_id
from src.provider_registry import get_primary_provider_contract
from tools.import_real_snapshot import OfflineImportError, import_bundle, main


def _page_payload(rows: list[dict], total: int) -> dict:
    return {"rc": 0, "data": {"total": total, "diff": rows}}


def _industry_rows(total: int = 128) -> list[dict]:
    return [
        {
            "f12": f"BK{idx:04d}",
            "f14": f"行业{idx:03d}",
            "f3": 0.1 * idx,
            "f62": float(idx * 10000),
            "f184": 1.2,
            "f66": float(idx),
            "f72": float(idx),
            "f78": float(idx),
            "f84": float(-idx),
            "f204": f"代表股{idx:03d}",
            "f205": f"{idx:06d}",
        }
        for idx in range(1, total + 1)
    ]


def _write_bundle(
    root: Path,
    *,
    jsonp: bool = False,
    total: int = 128,
    page_size: int = 50,
    trade_date: str = "2026-06-10",
    captured_at: str = "2026-06-10T10:00:00+08:00",
    rows: list[dict] | None = None,
    manifest_overrides: dict | None = None,
    mutate_page_bytes: bool = False,
) -> Path:
    bundle = root / "bundle"
    bundle.mkdir()
    rows = rows or _industry_rows(total)
    pages = []
    for page_number, start in enumerate(range(0, total, page_size), start=1):
        chunk = rows[start : start + page_size]
        payload = json.dumps(_page_payload(chunk, total), ensure_ascii=False)
        if jsonp:
            payload = f"jQuery_test_{page_number}({payload});"
        filename = f"page_{page_number:03d}.{'jsonp' if jsonp else 'json'}"
        path = bundle / filename
        path.write_text(payload, encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if mutate_page_bytes and page_number == 1:
            path.write_text(payload + "\n", encoding="utf-8")
        pages.append({"page_number": page_number, "filename": filename, "sha256": digest})
    primary = get_primary_provider_contract()
    manifest = {
        "manifest_version": "real_raw_response_bundle_v1",
        "provider_id": PRIMARY_PROVIDER_ID,
        "api_name": primary.api_name,
        "provider_contract_id": build_provider_contract_short_id(primary),
        "provider_contract_fingerprint": primary.to_dict()["semantic_contract_id"],
        "acquisition_method": "manual_raw_response_bundle",
        "operator_attested": True,
        "trade_date": trade_date,
        "captured_at": captured_at,
        "endpoint_host": "push2.eastmoney.com",
        "endpoint_path": "/api/qt/clist/get",
        "parameter_contract": {
            "fid": "f62",
            "po": 1,
            "pz": page_size,
            "np": 1,
            "fs": "m:90 s:4",
        },
        "expected_total": total,
        "page_size": page_size,
        "pages": pages,
    }
    manifest.update(manifest_overrides or {})
    (bundle / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return bundle


def test_synthetic_json_bundle_dry_run_passes_contract_pipeline(tmp_path):
    bundle = _write_bundle(tmp_path)
    result = import_bundle(bundle)
    assert result["write_status"] == "dry_run"
    assert result["written_rows"] == 0
    assert result["parsed_rows"] == 128
    assert result["normalized_rows"] == 128
    assert result["unique_bk_rows"] == 128
    assert result["operator_attested"] is True
    assert result["source_trust_model"] == "operator_attested"
    assert result["source_authenticity"] == "not_independently_verified"
    assert result["contract_qualification_verdict"] == "existing_contract_quality_and_eligibility_pipeline_passed"
    assert result["evidence_eligibility_verdict"] == "qualified_by_existing_evidence_pipeline"
    assert "qualified" not in result
    assert "qualification_verdict" not in result
    assert result["continuity_verdict"] == {"explicit_verified": 1}


def test_synthetic_jsonp_bundle_dry_run_passes_contract_pipeline(tmp_path):
    bundle = _write_bundle(tmp_path, jsonp=True)
    result = import_bundle(bundle)
    assert result["parsed_rows"] == 128
    assert result["write_status"] == "dry_run"


def test_sha256_mismatch_rejected(tmp_path):
    bundle = _write_bundle(tmp_path, mutate_page_bytes=True)
    with pytest.raises(OfflineImportError, match="sha256"):
        import_bundle(bundle)


def test_missing_page_rejected(tmp_path):
    bundle = _write_bundle(tmp_path)
    (bundle / "page_002.json").unlink()
    with pytest.raises(OfflineImportError, match="missing"):
        import_bundle(bundle)


def test_page_number_gap_rejected(tmp_path):
    bundle = _write_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pages"][1]["page_number"] = 4
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(OfflineImportError, match="continuous"):
        import_bundle(bundle)


def test_expected_total_mismatch_rejected(tmp_path):
    bundle = _write_bundle(tmp_path, manifest_overrides={"expected_total": 127})
    with pytest.raises(OfflineImportError, match="page count|expected_total"):
        import_bundle(bundle)


def test_duplicate_bk_code_rejected(tmp_path):
    rows = _industry_rows()
    rows[1]["f12"] = rows[0]["f12"]
    bundle = _write_bundle(tmp_path, rows=rows)
    with pytest.raises(OfflineImportError, match="unique"):
        import_bundle(bundle)


def test_stock_universe_rejected(tmp_path):
    rows = _industry_rows()
    for idx, row in enumerate(rows, start=1):
        row["f12"] = f"{idx:06d}"
    bundle = _write_bundle(tmp_path, rows=rows)
    with pytest.raises(OfflineImportError, match="stock universe"):
        import_bundle(bundle)


def test_wrong_provider_id_rejected(tmp_path):
    bundle = _write_bundle(tmp_path, manifest_overrides={"provider_id": "wrong_provider"})
    with pytest.raises(OfflineImportError, match="provider_id"):
        import_bundle(bundle)


def test_wrong_contract_fingerprint_rejected(tmp_path):
    bundle = _write_bundle(tmp_path, manifest_overrides={"provider_contract_fingerprint": "bad"})
    with pytest.raises(OfflineImportError, match="fingerprint"):
        import_bundle(bundle)


def test_sample_demo_mock_markers_rejected(tmp_path):
    bundle = _write_bundle(tmp_path, manifest_overrides={"acquisition_method": "sample"})
    with pytest.raises(OfflineImportError, match="SAMPLE"):
        import_bundle(bundle)


def test_missing_operator_attested_rejected(tmp_path):
    bundle = _write_bundle(tmp_path)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    del manifest["operator_attested"]
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(OfflineImportError, match="operator_attested"):
        import_bundle(bundle)


def test_operator_attested_false_rejected(tmp_path):
    bundle = _write_bundle(tmp_path, manifest_overrides={"operator_attested": False})
    with pytest.raises(OfflineImportError, match="operator_attested"):
        import_bundle(bundle)


def test_operator_attested_string_true_rejected(tmp_path):
    bundle = _write_bundle(tmp_path, manifest_overrides={"operator_attested": "true"})
    with pytest.raises(OfflineImportError, match="operator_attested"):
        import_bundle(bundle)


def test_wrong_acquisition_method_rejected(tmp_path):
    bundle = _write_bundle(tmp_path, manifest_overrides={"acquisition_method": "manual_csv_import"})
    with pytest.raises(OfflineImportError, match="acquisition_method"):
        import_bundle(bundle)


def test_non_trading_date_rejected(tmp_path):
    bundle = _write_bundle(tmp_path, trade_date="2026-06-13", captured_at="2026-06-13T10:00:00+08:00")
    with pytest.raises(OfflineImportError, match="eligible"):
        import_bundle(bundle)


def test_malformed_json_or_jsonp_rejected(tmp_path):
    bundle = _write_bundle(tmp_path)
    page = bundle / "page_001.json"
    page.write_text("callback({bad json});", encoding="utf-8")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    manifest["pages"][0]["sha256"] = hashlib.sha256(page.read_bytes()).hexdigest()
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(OfflineImportError, match="malformed"):
        import_bundle(bundle)


def test_missing_provenance_field_rejected(tmp_path):
    bundle = _write_bundle(tmp_path)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    del manifest["captured_at"]
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(OfflineImportError, match="missing"):
        import_bundle(bundle)


def test_dry_run_does_not_write_csv_sqlite_or_audit_log(tmp_path):
    bundle = _write_bundle(tmp_path)
    output_dir = tmp_path / "would_write_here"
    result = import_bundle(bundle, dry_run=True, write=False, output_dir=str(output_dir))
    assert result["write_status"] == "dry_run"
    assert not output_dir.exists()
    assert not list(tmp_path.glob("*.sqlite"))
    assert not list(tmp_path.glob("*.db"))
    assert not list(tmp_path.glob("*.log"))


def test_failure_path_leaves_no_partial_output(tmp_path):
    bundle = _write_bundle(tmp_path, mutate_page_bytes=True)
    output_dir = tmp_path / "output"
    with pytest.raises(OfflineImportError):
        import_bundle(bundle, output_dir=str(output_dir))
    assert not output_dir.exists()


def test_error_output_is_sanitized(capsys, tmp_path):
    bundle = _write_bundle(tmp_path, manifest_overrides={"cookie": "sensitive_cookie_value"})
    code = main(["--bundle", str(bundle)])
    out = capsys.readouterr().out
    assert code == 1
    assert "sensitive_cookie_value" not in out
    assert "forbidden_sensitive_metadata" in out


def test_cli_success_output_does_not_expose_absolute_bundle_path(capsys, tmp_path):
    bundle = _write_bundle(tmp_path)
    code = main(["--bundle", str(bundle)])
    out = capsys.readouterr().out
    assert code == 0
    assert str(bundle) not in out
    assert '"bundle_name": "bundle"' in out
    assert "not_independently_verified" in out


def test_cli_error_output_does_not_expose_absolute_user_path(capsys):
    user_path = "/Users/liujiayi/private/offline/bundle"
    code = main(["--bundle", user_path])
    out = capsys.readouterr().out
    assert code == 1
    assert user_path not in out
    assert "/Users/liujiayi" not in out


def test_dry_run_and_write_conflict_rejected(tmp_path):
    bundle = _write_bundle(tmp_path)
    with pytest.raises(OfflineImportError, match="cannot"):
        import_bundle(bundle, dry_run=True, write=True)


def test_write_without_acknowledgement_rejected(tmp_path):
    bundle = _write_bundle(tmp_path)
    with pytest.raises(OfflineImportError, match="acknowledge"):
        import_bundle(bundle, dry_run=False, write=True)


def test_acknowledgement_with_dry_run_rejected(tmp_path):
    bundle = _write_bundle(tmp_path)
    with pytest.raises(OfflineImportError, match="only valid"):
        import_bundle(bundle, dry_run=True, acknowledge_operator_attested_source=True)


def test_acknowledgement_does_not_bypass_hash_validation(monkeypatch, tmp_path):
    called = False

    def fake_append(*args, **kwargs):
        nonlocal called
        called = True
        return {"write_status": "written", "written_rows": 1}

    monkeypatch.setattr(importer, "append_snapshot_safely", fake_append)
    bundle = _write_bundle(tmp_path, mutate_page_bytes=True)
    with pytest.raises(OfflineImportError, match="sha256"):
        import_bundle(bundle, dry_run=False, write=True, acknowledge_operator_attested_source=True)
    assert called is False


def test_acknowledgement_does_not_bypass_contract_validation(monkeypatch, tmp_path):
    called = False

    def fake_append(*args, **kwargs):
        nonlocal called
        called = True
        return {"write_status": "written", "written_rows": 1}

    monkeypatch.setattr(importer, "append_snapshot_safely", fake_append)
    bundle = _write_bundle(tmp_path, manifest_overrides={"provider_contract_fingerprint": "bad"})
    with pytest.raises(OfflineImportError, match="fingerprint"):
        import_bundle(bundle, dry_run=False, write=True, acknowledge_operator_attested_source=True)
    assert called is False


def test_acknowledgement_does_not_bypass_sample_rejection(monkeypatch, tmp_path):
    called = False

    def fake_append(*args, **kwargs):
        nonlocal called
        called = True
        return {"write_status": "written", "written_rows": 1}

    monkeypatch.setattr(importer, "append_snapshot_safely", fake_append)
    bundle = _write_bundle(tmp_path, manifest_overrides={"acquisition_method": "sample"})
    with pytest.raises(OfflineImportError, match="SAMPLE"):
        import_bundle(bundle, dry_run=False, write=True, acknowledge_operator_attested_source=True)
    assert called is False


def test_write_payload_preserves_manual_bundle_provenance(monkeypatch, tmp_path):
    captured = {}

    def fake_output_path(*args, **kwargs):
        return str(tmp_path / "captured.csv")

    def fake_append(df, output_path, **kwargs):
        captured["df"] = df.copy()
        captured["output_path"] = output_path
        return {"write_status": "written", "written_rows": len(df), "output_path": output_path}

    monkeypatch.setattr(importer, "get_snapshot_output_path", fake_output_path)
    monkeypatch.setattr(importer, "append_snapshot_safely", fake_append)
    bundle = _write_bundle(tmp_path)
    result = import_bundle(bundle, dry_run=False, write=True, acknowledge_operator_attested_source=True)
    assert result["write_status"] == "written"
    payload = captured["df"]
    assert payload["acquisition_method"].unique().tolist() == ["manual_raw_response_bundle"]
    assert payload["source_trust_model"].unique().tolist() == ["operator_attested"]


def test_write_disabled_when_provenance_cannot_be_persisted(monkeypatch, tmp_path):
    called = False

    def fake_append(*args, **kwargs):
        nonlocal called
        called = True
        return {"write_status": "written", "written_rows": 1}

    monkeypatch.setattr(importer, "_write_provenance_persisted", lambda df: False)
    monkeypatch.setattr(importer, "append_snapshot_safely", fake_append)
    bundle = _write_bundle(tmp_path)
    with pytest.raises(OfflineImportError, match="write disabled"):
        import_bundle(bundle, dry_run=False, write=True, acknowledge_operator_attested_source=True)
    assert called is False


def test_validation_failure_never_calls_append_snapshot_safely(monkeypatch, tmp_path):
    called = False

    def fake_append(*args, **kwargs):
        nonlocal called
        called = True
        return {"write_status": "written", "written_rows": 1}

    monkeypatch.setattr(importer, "append_snapshot_safely", fake_append)
    bundle = _write_bundle(tmp_path)
    (bundle / "page_003.json").unlink()
    with pytest.raises(OfflineImportError, match="missing"):
        import_bundle(bundle, dry_run=False, write=True, acknowledge_operator_attested_source=True)
    assert called is False
