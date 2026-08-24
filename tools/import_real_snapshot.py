from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import TIMEZONE
from src.data_contracts import validate_real_snapshot_dataframe
from src.evidence_accumulation import build_evidence_accumulation_report
from src.market_session_policy import STATE_ELIGIBLE, evaluate_market_session_date
from src.provider_contracts import PRIMARY_PROVIDER_ID, build_provider_contract_short_id
from src.provider_registry import get_primary_provider_contract
from src.providers.akshare_sector_flow import normalize_provider_dataframe
from src.snapshot_quality import audit_snapshot_dataframe
from src.storage import append_snapshot_safely, get_snapshot_output_path


SUPPORTED_MANIFEST_VERSION = "real_raw_response_bundle_v1"
ALLOWED_ACQUISITION_METHODS = {"manual_raw_response_bundle"}
ENDPOINT_HOST = "push2.eastmoney.com"
ENDPOINT_PATH = "/api/qt/clist/get"
REQUIRED_MANIFEST_FIELDS = (
    "manifest_version",
    "provider_id",
    "api_name",
    "provider_contract_id",
    "provider_contract_fingerprint",
    "acquisition_method",
    "operator_attested",
    "trade_date",
    "captured_at",
    "endpoint_host",
    "endpoint_path",
    "parameter_contract",
    "expected_total",
    "page_size",
    "pages",
)
REQUIRED_PAGE_FIELDS = ("page_number", "filename", "sha256")
REQUIRED_PROVIDER_FIELDS = ("f12", "f14", "f62")
FORBIDDEN_MARKERS = ("sample", "demo", "mock", "synthetic", "generated")
FORBIDDEN_SENSITIVE_KEYS = (
    "cookie",
    "authorization",
    "bearer",
    "password",
    "proxy",
    "session",
    "clash",
    "token",
)
SECTOR_CODE_RE = re.compile(r"^BK\d+$")
STOCK_CODE_RE = re.compile(r"^\d{6}$")


class OfflineImportError(RuntimeError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sanitize_message(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"https?://[^\s\"')]+", "<url_redacted>", text)
    text = re.sub(r"(?i)(cookie|authorization|bearer|password|token)\s*[:=]\s*[^,;\\s]+", r"\1=<redacted>", text)
    text = re.sub(r"127\\.0\\.0\\.1:\\d+", "<local_proxy_redacted>", text)
    text = re.sub(r"/(?:Users|private|tmp|var|Volumes)/[^\s\"')]+", "<path_redacted>", text)
    return text[:500]


def _load_manifest(bundle_path: Path) -> tuple[dict[str, Any], str]:
    manifest_path = bundle_path / "manifest.json"
    if not manifest_path.exists():
        raise OfflineImportError("missing_manifest", "manifest.json is required.")
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise OfflineImportError("malformed_manifest", f"manifest.json is not valid JSON: {_sanitize_message(exc)}") from exc
    if not isinstance(manifest, dict):
        raise OfflineImportError("malformed_manifest", "manifest.json must contain a JSON object.")
    return manifest, _sha256_bytes(raw)


def _walk_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        items: list[str] = []
        for key, item in value.items():
            items.append(str(key))
            items.extend(_walk_values(item))
        return items
    if isinstance(value, list):
        items = []
        for item in value:
            items.extend(_walk_values(item))
        return items
    return [str(value)]


def _assert_no_sensitive_or_demo_markers(payload: Any, *, context: str) -> None:
    texts = _walk_values(payload)
    lowered = [item.lower() for item in texts]
    for text in lowered:
        if any(marker in text for marker in FORBIDDEN_MARKERS):
            raise OfflineImportError("forbidden_demo_marker", f"{context} contains SAMPLE/DEMO/MOCK/SYNTHETIC markers.")
    for text in lowered:
        if any(key in text for key in FORBIDDEN_SENSITIVE_KEYS):
            raise OfflineImportError("forbidden_sensitive_metadata", f"{context} contains forbidden sensitive metadata keys.")
        if "127.0.0.1" in text or "localhost:" in text:
            raise OfflineImportError("forbidden_sensitive_metadata", f"{context} contains local proxy metadata.")


def _validate_manifest(manifest: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest]
    if missing:
        raise OfflineImportError("missing_provenance", f"manifest missing required fields: {', '.join(missing)}")
    _assert_no_sensitive_or_demo_markers(manifest, context="manifest")
    if manifest.get("manifest_version") != SUPPORTED_MANIFEST_VERSION:
        raise OfflineImportError("unsupported_manifest_version", "manifest_version is not supported.")
    if manifest.get("acquisition_method") not in ALLOWED_ACQUISITION_METHODS:
        raise OfflineImportError("invalid_acquisition_method", "acquisition_method is not allowed for REAL offline import.")
    if manifest.get("operator_attested") is not True:
        raise OfflineImportError("operator_attestation_required", "operator_attested must be JSON boolean true.")
    if manifest.get("provider_id") != PRIMARY_PROVIDER_ID:
        raise OfflineImportError("provider_identity_mismatch", "provider_id does not match the accepted REAL provider contract.")
    primary = get_primary_provider_contract()
    if manifest.get("api_name") != primary.api_name:
        raise OfflineImportError("provider_identity_mismatch", "api_name does not match the accepted REAL provider contract.")
    if manifest.get("provider_contract_id") != build_provider_contract_short_id(primary):
        raise OfflineImportError("provider_contract_mismatch", "provider_contract_id does not match the accepted REAL provider contract.")
    if manifest.get("provider_contract_fingerprint") != primary.to_dict().get("semantic_contract_id"):
        raise OfflineImportError("provider_contract_mismatch", "provider_contract_fingerprint does not match the accepted REAL provider contract.")
    if manifest.get("endpoint_host") != ENDPOINT_HOST or manifest.get("endpoint_path") != ENDPOINT_PATH:
        raise OfflineImportError("endpoint_mismatch", "endpoint host/path does not match the accepted Eastmoney raw-response endpoint.")
    if not isinstance(manifest.get("parameter_contract"), dict):
        raise OfflineImportError("missing_provenance", "parameter_contract must be an object.")
    if not isinstance(manifest.get("pages"), list) or not manifest.get("pages"):
        raise OfflineImportError("missing_pages", "manifest pages must be a non-empty list.")
    try:
        expected_total = int(manifest.get("expected_total"))
        page_size = int(manifest.get("page_size"))
    except Exception as exc:
        raise OfflineImportError("invalid_manifest_numbers", "expected_total and page_size must be integers.") from exc
    if expected_total <= 0 or page_size <= 0:
        raise OfflineImportError("invalid_manifest_numbers", "expected_total and page_size must be positive.")
    expected_page_count = (expected_total + page_size - 1) // page_size
    if len(manifest["pages"]) != expected_page_count:
        raise OfflineImportError("page_coverage_mismatch", "manifest page count does not cover expected_total/page_size.")
    page_numbers = []
    filenames = []
    for item in manifest["pages"]:
        if not isinstance(item, dict):
            raise OfflineImportError("invalid_page_manifest", "each pages item must be an object.")
        missing = [field for field in REQUIRED_PAGE_FIELDS if field not in item]
        if missing:
            raise OfflineImportError("invalid_page_manifest", f"page manifest missing fields: {', '.join(missing)}")
        page_numbers.append(int(item["page_number"]))
        filenames.append(str(item["filename"]))
    if sorted(page_numbers) != list(range(1, expected_page_count + 1)):
        raise OfflineImportError("page_number_gap", "page_number values must be continuous from 1.")
    if len(set(page_numbers)) != len(page_numbers) or len(set(filenames)) != len(filenames):
        raise OfflineImportError("duplicate_pages", "page_number and filename values must be unique.")


def _page_path(bundle_path: Path, filename: str) -> Path:
    if Path(filename).is_absolute():
        raise OfflineImportError("invalid_page_path", "page filename must be relative to the bundle.")
    path = (bundle_path / filename).resolve()
    try:
        path.relative_to(bundle_path.resolve())
    except ValueError as exc:
        raise OfflineImportError("invalid_page_path", "page filename must stay inside the bundle.") from exc
    return path


def _parse_json_or_jsonp(text: str, filename: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise OfflineImportError("malformed_page", f"{filename} is empty.")
    if stripped.startswith("{"):
        payload = stripped
    else:
        start = stripped.find("(")
        end = stripped.rfind(")")
        if start <= 0 or end <= start:
            raise OfflineImportError("malformed_page", f"{filename} is not valid JSON or JSONP.")
        payload = stripped[start + 1 : end].strip()
    try:
        data = json.loads(payload)
    except Exception as exc:
        raise OfflineImportError("malformed_page", f"{filename} JSON payload is malformed: {_sanitize_message(exc)}") from exc
    if not isinstance(data, dict):
        raise OfflineImportError("malformed_page", f"{filename} payload must be a JSON object.")
    return data


def _load_pages(bundle_path: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    expected_total = int(manifest["expected_total"])
    page_size = int(manifest["page_size"])
    for page in sorted(manifest["pages"], key=lambda item: int(item["page_number"])):
        filename = str(page["filename"])
        path = _page_path(bundle_path, filename)
        if not path.exists():
            raise OfflineImportError("missing_page_file", f"page file is missing: {filename}")
        raw = path.read_bytes()
        if _sha256_bytes(raw) != str(page["sha256"]).lower():
            raise OfflineImportError("sha256_mismatch", f"page sha256 does not match: {filename}")
        text = raw.decode("utf-8")
        payload = _parse_json_or_jsonp(text, filename)
        if payload.get("rc") != 0:
            raise OfflineImportError("provider_rc_failed", f"{filename} rc is not 0.")
        data = payload.get("data")
        if not isinstance(data, dict) or "diff" not in data:
            raise OfflineImportError("schema_drift", f"{filename} missing data.diff.")
        if int(data.get("total", -1)) != expected_total:
            raise OfflineImportError("expected_total_mismatch", f"{filename} reported total does not match manifest expected_total.")
        diff = data.get("diff")
        if not isinstance(diff, list):
            raise OfflineImportError("schema_drift", f"{filename} data.diff must be a list.")
        if int(page["page_number"]) < len(manifest["pages"]) and len(diff) > page_size:
            raise OfflineImportError("page_size_mismatch", f"{filename} has more rows than page_size.")
        _assert_no_sensitive_or_demo_markers(diff, context=filename)
        rows.extend([dict(item) for item in diff if isinstance(item, dict)])
    return rows


def _validate_rows(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> pd.DataFrame:
    expected_total = int(manifest["expected_total"])
    if len(rows) != expected_total:
        raise OfflineImportError("expected_total_mismatch", "merged row count does not match expected_total.")
    raw_df = pd.DataFrame(rows)
    missing_fields = [field for field in REQUIRED_PROVIDER_FIELDS if field not in raw_df.columns]
    if missing_fields:
        raise OfflineImportError("schema_drift", f"raw rows missing provider fields: {', '.join(missing_fields)}")
    codes = raw_df["f12"].fillna("").astype(str).str.strip()
    names = raw_df["f14"].fillna("").astype(str).str.strip()
    if names.eq("").any():
        raise OfflineImportError("schema_drift", "sector names must be non-empty.")
    if codes.duplicated().any():
        raise OfflineImportError("duplicate_sector_code", "sector code must be unique across merged pages.")
    bk_count = int(codes.map(lambda value: bool(SECTOR_CODE_RE.match(value))).sum())
    stock_code_count = int(codes.map(lambda value: bool(STOCK_CODE_RE.match(value))).sum())
    if stock_code_count:
        raise OfflineImportError("stock_universe_rejected", "raw rows look like stock universe, not industry board universe.")
    if bk_count != len(codes):
        raise OfflineImportError("industry_universe_rejected", "sector code must match BK-prefixed Eastmoney board codes.")
    return raw_df


def _validate_trade_date(manifest: dict[str, Any]) -> dict[str, Any]:
    trade_date = str(manifest["trade_date"])
    try:
        captured_at = pd.Timestamp(manifest["captured_at"])
    except Exception as exc:
        raise OfflineImportError("invalid_captured_at", "captured_at must be a parseable timestamp.") from exc
    if captured_at.tzinfo is None:
        captured_at = captured_at.tz_localize(TIMEZONE)
    else:
        captured_at = captured_at.tz_convert(TIMEZONE)
    if captured_at.strftime("%Y-%m-%d") != trade_date:
        raise OfflineImportError("captured_at_trade_date_mismatch", "captured_at local date must match trade_date.")
    decision = evaluate_market_session_date(trade_date)
    if decision.get("market_session_date_state") != STATE_ELIGIBLE:
        raise OfflineImportError("market_session_date_ineligible", "trade_date is not eligible under bundled market-session calendar.")
    return {"captured_at": captured_at.to_pydatetime(), "date_decision": decision}


def _build_provider_shaped_frame(raw_df: pd.DataFrame) -> pd.DataFrame:
    return raw_df.copy()


def _apply_offline_provenance(normalized: pd.DataFrame, manifest: dict[str, Any]) -> pd.DataFrame:
    enriched = normalized.copy()
    enriched["acquisition_method"] = manifest["acquisition_method"]
    enriched["operator_attested"] = True
    enriched["source_trust_model"] = "operator_attested"
    enriched["source_authenticity"] = "not_independently_verified"
    return enriched


def _write_provenance_persisted(df: pd.DataFrame) -> bool:
    required = {"acquisition_method", "source_trust_model"}
    return required.issubset(set(df.columns))


def _run_existing_pipeline(raw_df: pd.DataFrame, manifest: dict[str, Any], bundle_path: Path) -> dict[str, Any]:
    date_info = _validate_trade_date(manifest)
    normalized_result = normalize_provider_dataframe(
        _build_provider_shaped_frame(raw_df),
        sector_type="行业资金流",
        indicator="今日",
        captured_at=date_info["captured_at"],
        strict_schema=True,
    )
    normalized = _apply_offline_provenance(normalized_result.normalized_df, manifest)
    contract = validate_real_snapshot_dataframe(normalized, context="offline_real_bundle_import")
    if not contract.get("contract_ok"):
        raise OfflineImportError("real_contract_failed", "normalized REAL snapshot failed existing data contract.")
    quality = audit_snapshot_dataframe(normalized, source_label="offline_real_bundle_import")
    if quality.get("errors"):
        raise OfflineImportError("quality_audit_failed", "normalized REAL snapshot failed existing quality audit.")
    with tempfile.TemporaryDirectory(prefix="fund-flow-offline-import-") as tmp:
        tmp_path = Path(tmp)
        tmp_file = tmp_path / f"sector_flow_{manifest['trade_date']}.csv"
        normalized.to_csv(tmp_file, index=False)
        evidence = build_evidence_accumulation_report(
            source_mode="REAL",
            data_dir=tmp_path,
            cell_minutes=30,
        )
    qualified = int(evidence.get("qualified_capture_event_count", 0) or 0) > 0
    if not qualified:
        raise OfflineImportError("qualification_failed", "normalized REAL snapshot did not become qualified evidence.")
    return {
        "bundle_name": bundle_path.name,
        "acquisition_method": manifest["acquisition_method"],
        "operator_attested": True,
        "source_trust_model": "operator_attested",
        "source_authenticity": "not_independently_verified",
        "provider_id": manifest["provider_id"],
        "api_name": manifest["api_name"],
        "contract_id": manifest["provider_contract_id"],
        "contract_fingerprint": manifest["provider_contract_fingerprint"],
        "expected_total": int(manifest["expected_total"]),
        "parsed_rows": int(len(raw_df)),
        "normalized_rows": int(len(normalized)),
        "unique_bk_rows": int(normalized["sector_code"].nunique()),
        "contract_qualification_verdict": "existing_contract_quality_and_eligibility_pipeline_passed",
        "quality_verdict": quality.get("quality_label"),
        "evidence_eligibility_verdict": "qualified_by_existing_evidence_pipeline",
        "continuity_verdict": evidence.get("provider_contract_resolution_counts", {}),
        "market_session_date_state": date_info["date_decision"].get("market_session_date_state"),
        "calendar_policy_identity": date_info["date_decision"].get("calendar_policy_identity"),
        "normalization_status": normalized_result.diagnostic.get("normalization_status"),
        "normalized_df": normalized,
    }


def inspect_bundle(bundle: str | Path) -> dict[str, Any]:
    bundle_path = Path(bundle).expanduser().resolve()
    if not bundle_path.exists() or not bundle_path.is_dir():
        raise OfflineImportError("bundle_not_found", "bundle path must be an existing directory.")
    manifest, manifest_hash = _load_manifest(bundle_path)
    _validate_manifest(manifest)
    rows = _load_pages(bundle_path, manifest)
    raw_df = _validate_rows(rows, manifest)
    result = _run_existing_pipeline(raw_df, manifest, bundle_path)
    result["manifest_hash"] = manifest_hash
    return result


def import_bundle(
    bundle: str | Path,
    *,
    dry_run: bool = True,
    write: bool = False,
    acknowledge_operator_attested_source: bool = False,
    output_dir: str = "data/ticks",
) -> dict[str, Any]:
    if dry_run and write:
        raise OfflineImportError("cli_argument_conflict", "--dry-run and --write cannot be used together.")
    if dry_run and acknowledge_operator_attested_source:
        raise OfflineImportError("cli_argument_conflict", "source acknowledgement is only valid with --write.")
    if write and not acknowledge_operator_attested_source:
        raise OfflineImportError("operator_acknowledgement_required", "--write requires --acknowledge-operator-attested-source.")
    result = inspect_bundle(bundle)
    normalized = result.pop("normalized_df")
    if dry_run or not write:
        result.update({"write_status": "dry_run", "written_rows": 0})
        return result
    if not _write_provenance_persisted(normalized):
        raise OfflineImportError(
            "WRITE_DISABLED_PROVENANCE_NOT_PERSISTED",
            "write disabled because acquisition_method/source_trust_model would not be persisted.",
        )
    output_path = get_snapshot_output_path(data_date=str(normalized["trade_date"].iloc[0]), directory=output_dir)
    write_result = append_snapshot_safely(
        normalized,
        output_path,
        dedupe_keys=["captured_at", "sector_type", "sector_name"],
        force=False,
    )
    result.update(write_result)
    return result


def _failure_payload(exc: OfflineImportError) -> dict[str, Any]:
    return {
        "import_status": "failed",
        "error_category": exc.category,
        "error": _sanitize_message(str(exc)),
        "write_status": "blocked",
        "written_rows": 0,
    }


def _safe_json_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            safe[key] = _sanitize_message(value)
        else:
            safe[key] = value
    return safe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fail-closed offline REAL raw-response bundle importer.")
    parser.add_argument("--bundle", required=True, help="Path to a raw-response bundle directory.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing REAL CSV. This is the default.")
    parser.add_argument("--write", action="store_true", help="Explicitly write the normalized REAL snapshot after all checks pass.")
    parser.add_argument(
        "--acknowledge-operator-attested-source",
        action="store_true",
        help="Required with --write; confirms source is operator-attested and not independently verified.",
    )
    parser.add_argument("--output-dir", default="data/ticks", help="Output directory used only with --write.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dry_run = bool(args.dry_run or not args.write)
    try:
        result = import_bundle(
            args.bundle,
            dry_run=dry_run,
            write=bool(args.write),
            acknowledge_operator_attested_source=bool(args.acknowledge_operator_attested_source),
            output_dir=args.output_dir,
        )
    except OfflineImportError as exc:
        print(json.dumps(_failure_payload(exc), ensure_ascii=False, indent=2))
        return 1
    safe = _safe_json_payload({key: value for key, value in result.items() if key != "normalized_df"})
    safe["import_status"] = "passed"
    print(json.dumps(safe, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
