from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.release_readiness import (  # noqa: E402
    build_release_readiness_report,
    render_release_readiness_markdown,
    validate_release_readiness_text,
)
try:
    from src.runtime_profile import get_runtime_profile, validate_runtime_profile_text  # noqa: E402
except Exception:  # pragma: no cover - defensive CLI fallback
    get_runtime_profile = None
    validate_runtime_profile_text = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行公开发布前 release readiness 审计。")
    parser.add_argument("--write-report", default="", help="可选：写入 docs/ 下的 Markdown 报告。")
    parser.add_argument("--strict", action="store_true", help="存在 error 时返回非零退出码。")
    parser.add_argument("--quiet", action="store_true", help="减少命令行输出。")
    return parser


def _resolve_report_path(path_text: str) -> Path:
    path = Path(path_text)
    path = path if path.is_absolute() else PROJECT_ROOT / path
    resolved = path.resolve()
    docs_root = (PROJECT_ROOT / "docs").resolve()
    if docs_root not in resolved.parents and resolved != docs_root:
        raise ValueError("--write-report 只能写入 docs/ 目录下的 Markdown 文件。")
    if resolved.suffix.lower() != ".md":
        raise ValueError("--write-report 只允许 Markdown 文件。")
    return resolved


def run_release_check(write_report: str = "", strict: bool = False, quiet: bool = False) -> dict:
    report = build_release_readiness_report(PROJECT_ROOT)
    runtime_profile = {}
    runtime_forbidden_hits: list[str] = []
    if get_runtime_profile is None:
        report.setdefault("warnings", []).append("runtime_profile.py 不可用，建议运行 python tools/cloud_preflight.py 进一步检查。")
    else:
        try:
            runtime_profile = get_runtime_profile(PROJECT_ROOT)
            if validate_runtime_profile_text is not None:
                runtime_forbidden_hits = validate_runtime_profile_text(runtime_profile.get("runtime_reason", ""))
        except Exception as exc:  # pragma: no cover - defensive CLI fallback
            report.setdefault("warnings", []).append(f"runtime profile 检查失败：{exc}")
    report["runtime_profile_label"] = runtime_profile.get("runtime_label", "未检查")
    report["public_demo_hint"] = "公开演示可设置 FUND_FLOW_PUBLIC_DEMO=1，默认进入 SAMPLE 和作品集演示模式。"
    report["cloud_preflight_hint"] = "运行 python tools/cloud_preflight.py 可检查 Streamlit Cloud / public demo 首次访问准备度。"
    report["runtime_profile_forbidden_hits"] = runtime_forbidden_hits
    markdown = render_release_readiness_markdown(report)
    report_forbidden_hits = validate_release_readiness_text(markdown)
    report["rendered_report_forbidden_hits"] = report_forbidden_hits
    output_path = ""
    if write_report:
        path = _resolve_report_path(write_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        output_path = str(path)
    report["written_report_path"] = output_path
    report["exit_code"] = 1 if strict and report.get("error_count", 0) else 0

    if not quiet:
        links = report.get("markdown_link_report", {})
        assets = report.get("public_assets", {})
        sample_contract = report.get("sample_data_contract", {})
        print("Release readiness check")
        print(f"  readiness_label: {report.get('readiness_label')}")
        print(f"  warning_count: {report.get('warning_count')}")
        print(f"  error_count: {report.get('error_count')}")
        print(f"  app_version: {report.get('app_version')}")
        print(f"  changelog_version_ok: {report.get('changelog_version_ok')}")
        print(f"  tracked_forbidden_files: {report.get('tracked_forbidden_files', [])}")
        print(f"  sample_data_contract_label: {sample_contract.get('sample_data_contract_label')}")
        print(f"  sample_data_contract_rows: {sample_contract.get('row_count')}")
        print(f"  missing_assets: {assets.get('missing_assets', [])}")
        print(f"  missing_links: {links.get('missing_links', [])}")
        print(f"  local_path_hits: {report.get('local_path_hits', [])}")
        print(f"  forbidden_phrase_hits: {report.get('forbidden_phrase_hits', [])}")
        print(f"  rendered_report_forbidden_hits: {report_forbidden_hits}")
        print(f"  runtime_profile_label: {report.get('runtime_profile_label')}")
        print(f"  public_demo_hint: {report.get('public_demo_hint')}")
        print(f"  cloud_preflight_hint: {report.get('cloud_preflight_hint')}")
        print(f"  runtime_profile_forbidden_hits: {runtime_forbidden_hits}")
        print("  next_manual_checks:")
        print("    - SAMPLE + 作品集演示模式浏览核心页面。")
        print("    - 检查 demo brief 和观察简报下载内容。")
        print("    - 运行 git status，确认真实 CSV、SQLite、secrets 和 venv 未进入提交。")
        if output_path:
            print(f"  written_report_path: {output_path}")
    return report


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_release_check(args.write_report, args.strict, args.quiet)
    except Exception as exc:
        if not args.quiet:
            print(f"release_check failed: {exc}")
        return 1
    return int(report.get("exit_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
