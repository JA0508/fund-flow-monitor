from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.provider_network_diagnostics import build_provider_network_diagnosis, validate_network_diagnostic_text  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose provider network path without printing proxy values.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--skip-akshare", action="store_true", help="Skip AKShare provider probe stage.")
    parser.add_argument("--skip-http", action="store_true", help="Skip HTTP reachability stage.")
    parser.add_argument("--quiet", action="store_true", help="Reduce text output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_provider_network_diagnosis(include_akshare=not args.skip_akshare, include_http=not args.skip_http)
    hits = validate_network_diagnostic_text(json.dumps(report, ensure_ascii=False))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif not args.quiet:
        print("Provider network diagnosis")
        print(f"  final_classification: {report.get('final_classification')}")
        print("  proxy presence:")
        for key, value in (report.get("proxy_presence_flags") or {}).items():
            print(f"    {key}: {bool(value)}")
        for stage in report.get("stages", []):
            print(f"  {stage.get('stage')}: success={stage.get('success')} error={stage.get('error_type')} message={stage.get('message')}")
    if hits:
        print(f"forbidden_hits: {hits}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
