from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DEFAULT_SECTOR_TYPE  # noqa: E402
from src.data_contracts import validate_real_snapshot_dataframe  # noqa: E402
from src.providers.akshare_sector_flow import (  # noqa: E402
    API_NAME,
    ProviderBoundaryError,
    fetch_and_normalize_sector_flow,
)
from src.utils import get_china_now  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="诊断 AKShare 行业/概念资金流 provider 边界，不写 data/ticks。",
    )
    parser.add_argument("--sector-type", default=DEFAULT_SECTOR_TYPE, help="板块类型，默认行业资金流。")
    parser.add_argument("--indicator", default="今日", help="AKShare indicator，默认 今日。")
    parser.add_argument("--attempts", type=int, default=1, help="网络/超时错误最多尝试次数，默认 1，最大 3。")
    parser.add_argument("--json", action="store_true", help="输出 JSON 诊断结果。")
    parser.add_argument("--raw-columns", action="store_true", help="在文本模式显示返回列名。")
    parser.add_argument("--quiet", action="store_true", help="减少文本输出。")
    return parser


def _akshare_version() -> str:
    try:
        import akshare as ak

        return str(getattr(ak, "__version__", "unknown"))
    except Exception:
        return "unavailable"


def run_probe(args: argparse.Namespace) -> dict:
    ak_version = _akshare_version()
    result: dict = {
        "akshare_version": ak_version,
        "api_name": API_NAME,
        "sector_type": args.sector_type,
        "indicator": args.indicator,
        "success": False,
        "failure_category": None,
        "exception_type": None,
        "message": None,
        "contract_ok": None,
        "contract_label": None,
        "diagnostic": {},
    }
    try:
        provider_result = fetch_and_normalize_sector_flow(
            sector_type=args.sector_type,
            indicator=args.indicator,
            captured_at=get_china_now(),
            attempts=args.attempts,
        )
        normalized = provider_result.normalized_df
        contract = validate_real_snapshot_dataframe(normalized, context="probe_akshare")
        diagnostic = dict(provider_result.diagnostic)
        diagnostic["contract_status"] = contract.get("contract_label")
        result.update(
            {
                "success": bool(contract.get("contract_ok")),
                "failure_category": None if contract.get("contract_ok") else "contract_error",
                "message": "AKShare provider fetch / normalize / contract probe completed.",
                "contract_ok": bool(contract.get("contract_ok")),
                "contract_label": contract.get("contract_label"),
                "normalized_row_count": int(len(normalized)) if normalized is not None else 0,
                "diagnostic": diagnostic,
                "warnings": list(contract.get("warnings") or []),
                "errors": list(contract.get("errors") or []),
            }
        )
    except ProviderBoundaryError as exc:
        result.update(
            {
                "success": False,
                "failure_category": exc.category,
                "exception_type": type(exc.original).__name__ if exc.original is not None else type(exc).__name__,
                "message": str(exc),
                "diagnostic": exc.diagnostic,
                "warnings": [],
                "errors": [str(exc)],
            }
        )
    except Exception as exc:
        result.update(
            {
                "success": False,
                "failure_category": "provider_error",
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "warnings": [],
                "errors": [str(exc)],
            }
        )
    return result


def _print_text(result: dict, raw_columns: bool = False, quiet: bool = False) -> None:
    if quiet:
        return
    diagnostic = result.get("diagnostic") or {}
    print("AKShare provider probe")
    print(f"akshare_version: {result.get('akshare_version')}")
    print(f"api_name: {result.get('api_name')}")
    print(f"sector_type: {result.get('sector_type')}")
    print(f"indicator: {result.get('indicator')}")
    print(f"success: {result.get('success')}")
    print(f"failure_category: {result.get('failure_category')}")
    print(f"exception_type: {result.get('exception_type')}")
    print(f"message: {result.get('message')}")
    print(f"response_type: {diagnostic.get('response_type')}")
    print(f"row_count: {diagnostic.get('row_count')}")
    print(f"schema_fingerprint: {diagnostic.get('schema_fingerprint')}")
    print(f"normalization_status: {diagnostic.get('normalization_status')}")
    print(f"contract_label: {result.get('contract_label')}")
    print(f"retry_count: {diagnostic.get('retry_count', 0)}")
    if raw_columns:
        print(f"columns: {diagnostic.get('column_names', [])}")
    warnings = result.get("warnings") or []
    errors = result.get("errors") or []
    if warnings:
        print("warnings:")
        for item in warnings:
            print(f"  - {item}")
    if errors:
        print("errors:")
        for item in errors:
            print(f"  - {item}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_probe(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    else:
        _print_text(result, raw_columns=args.raw_columns, quiet=args.quiet)
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())

