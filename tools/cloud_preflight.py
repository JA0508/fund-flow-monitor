from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.release_readiness import (  # noqa: E402
    check_gitignore_safety,
    scan_markdown_links,
    scan_text_for_forbidden_investment_phrases,
    scan_text_for_local_paths,
)
from src.runtime_profile import (  # noqa: E402
    get_runtime_profile,
    validate_runtime_profile_text,
)
from src.data_contracts import validate_snapshot_directory  # noqa: E402


REQUIRED_ASSETS = (
    "app.py",
    "requirements.txt",
    ".streamlit/config.toml",
    ".streamlit/secrets.example.toml",
    "docs/demo_briefs/sample_observation_brief.md",
    "docs/ARCHITECTURE.md",
    "docs/DATA_FLOW.md",
    "docs/OPERATIONS.md",
    "README.md",
    "tools/release_check.py",
    "tools/quality_gate.py",
    "src/runtime_profile.py",
    "src/data_contracts.py",
)


def _count_pngs(path: Path) -> int:
    return len(list(path.glob("*.png"))) + len(list((path / "assets").glob("*.png"))) if path.exists() else 0


def _has_sample_csv(root: Path) -> bool:
    sample_dir = root / "sample_data/ticks"
    return sample_dir.exists() and any(sample_dir.glob("*.csv"))


def _with_public_demo_env(enabled: bool):
    class _EnvContext:
        def __enter__(self):
            self.old_value = os.environ.get("FUND_FLOW_PUBLIC_DEMO")
            if enabled:
                os.environ["FUND_FLOW_PUBLIC_DEMO"] = "1"
            return self

        def __exit__(self, exc_type, exc, tb):
            if enabled:
                if self.old_value is None:
                    os.environ.pop("FUND_FLOW_PUBLIC_DEMO", None)
                else:
                    os.environ["FUND_FLOW_PUBLIC_DEMO"] = self.old_value
            return False

    return _EnvContext()


def build_cloud_preflight_report(project_root: str | Path = ".", public_demo_env: bool = False) -> dict:
    root = Path(project_root)
    warnings: list[str] = []
    errors: list[str] = []
    missing_assets = [path for path in REQUIRED_ASSETS if not (root / path).exists()]
    if missing_assets:
        errors.append("公开演示缺少必要文件。")

    sample_data_available = _has_sample_csv(root)
    if not sample_data_available:
        errors.append("sample_data/ticks 缺少可复现演示 CSV。")
    sample_contract = validate_snapshot_directory(root / "sample_data/ticks", sample=True)
    if sample_contract.get("error_count", 0):
        errors.append("sample_data/ticks 未通过轻量数据契约检查。")
    warnings.extend(sample_contract.get("warnings", []))

    screenshot_dir = root / "docs/screenshots"
    screenshot_count = _count_pngs(screenshot_dir)
    if not screenshot_dir.exists():
        errors.append("docs/screenshots 目录不存在。")
    elif screenshot_count == 0:
        warnings.append("docs/screenshots 暂未发现 PNG 截图；可先依赖截图指南。")

    demo_brief_available = (root / "docs/demo_briefs/sample_observation_brief.md").exists()
    if not demo_brief_available:
        errors.append("缺少 SAMPLE demo brief。")

    with _with_public_demo_env(public_demo_env):
        runtime_profile = get_runtime_profile(root)
    runtime_errors = list(runtime_profile.get("errors", []))
    runtime_warnings = list(runtime_profile.get("warnings", []))
    errors.extend(runtime_errors)
    warnings.extend(runtime_warnings)
    public_demo_default_source = runtime_profile.get("default_data_source_mode")
    if public_demo_env and sample_data_available and public_demo_default_source != "SAMPLE":
        errors.append("FUND_FLOW_PUBLIC_DEMO=1 时默认数据源未指向 SAMPLE。")

    gitignore_safety = check_gitignore_safety(root)
    warnings.extend(gitignore_safety.get("warnings", []))
    errors.extend(gitignore_safety.get("errors", []))

    readme_path = root / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
    local_path_hits = scan_text_for_local_paths(readme_text)
    if local_path_hits:
        errors.append("README 中存在本地路径风险。")
    readme_links = scan_markdown_links(readme_text, root) if readme_text else {
        "links_checked": 0,
        "existing_links": [],
        "missing_links": [],
        "external_links": [],
        "anchor_links": [],
    }
    if readme_links.get("missing_links"):
        errors.append("README 存在缺失的相对链接。")

    forbidden_hits = scan_text_for_forbidden_investment_phrases(readme_text)
    if forbidden_hits:
        errors.append("README 存在动作性投资表达风险。")
    runtime_forbidden = validate_runtime_profile_text(runtime_profile.get("runtime_reason", ""))
    forbidden_hits = sorted(set(forbidden_hits + runtime_forbidden))

    secrets_required = False
    if "secrets.toml" in readme_text and "secrets.example.toml" not in readme_text:
        secrets_required = True
        warnings.append("README 可能让用户误以为必须配置 secrets.toml。")

    warning_count = len(warnings)
    error_count = len(errors)
    cloud_ready = error_count == 0
    if cloud_ready and warning_count == 0:
        label = "云端公开演示预检通过"
        reason = "公开演示所需 SAMPLE、文档、配置和 runtime profile 均可用。"
    elif cloud_ready:
        label = "云端公开演示存在轻微警告"
        reason = "关键检查通过，但仍有可读性或截图资产提示。"
    else:
        label = "云端公开演示需修复"
        reason = "存在缺失资产、链接、本地路径或 runtime profile 配置问题。"

    return {
        "cloud_ready": cloud_ready,
        "cloud_readiness_label": label,
        "cloud_readiness_reason": reason,
        "warning_count": warning_count,
        "error_count": error_count,
        "sample_data_available": sample_data_available,
        "screenshot_count": screenshot_count,
        "demo_brief_available": demo_brief_available,
        "runtime_profile_label": runtime_profile.get("runtime_label"),
        "public_demo_default_source": public_demo_default_source,
        "runtime_profile": runtime_profile,
        "sample_data_contract_label": sample_contract.get("contract_label"),
        "sample_data_contract_ok": sample_contract.get("contract_ok"),
        "sample_data_contract_rows": sample_contract.get("row_count", 0),
        "missing_assets": missing_assets,
        "missing_links": readme_links.get("missing_links", []),
        "local_path_hits": local_path_hits,
        "forbidden_hits": forbidden_hits,
        "gitignore_safety_label": gitignore_safety.get("gitignore_label"),
        "secrets_required": secrets_required,
        "warnings": warnings,
        "errors": errors,
        "next_manual_checks": [
            "FUND_FLOW_PUBLIC_DEMO=1 streamlit run app.py 后确认默认进入 SAMPLE 和作品集演示模式。",
            "确认页面不写 data/ticks，也不自动创建 data/warehouse/fund_flow.sqlite。",
            "确认 SAMPLE、demo brief、截图指南和 README 均明确不代表真实行情。",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行 Streamlit Cloud / public demo 预检。")
    parser.add_argument("--strict", action="store_true", help="存在 error 时返回非零退出码。")
    parser.add_argument("--quiet", action="store_true", help="减少命令行输出。")
    parser.add_argument("--public-demo-env", action="store_true", help="模拟 FUND_FLOW_PUBLIC_DEMO=1。")
    return parser


def run_cloud_preflight(strict: bool = False, quiet: bool = False, public_demo_env: bool = False) -> dict:
    report = build_cloud_preflight_report(PROJECT_ROOT, public_demo_env=public_demo_env)
    report["exit_code"] = 1 if strict and report.get("error_count", 0) else 0
    if not quiet:
        print("Cloud preflight check")
        print(f"  cloud_readiness_label: {report.get('cloud_readiness_label')}")
        print(f"  warning_count: {report.get('warning_count')}")
        print(f"  error_count: {report.get('error_count')}")
        print(f"  sample_data_available: {report.get('sample_data_available')}")
        print(f"  screenshot_count: {report.get('screenshot_count')}")
        print(f"  demo_brief_available: {report.get('demo_brief_available')}")
        print(f"  sample_data_contract_label: {report.get('sample_data_contract_label')}")
        print(f"  sample_data_contract_rows: {report.get('sample_data_contract_rows')}")
        print(f"  runtime_profile_label: {report.get('runtime_profile_label')}")
        print(f"  public_demo_default_source: {report.get('public_demo_default_source')}")
        print(f"  missing_assets: {report.get('missing_assets')}")
        print(f"  missing_links: {report.get('missing_links')}")
        print(f"  forbidden_hits: {report.get('forbidden_hits')}")
        print("  next_manual_checks:")
        for item in report.get("next_manual_checks", []):
            print(f"    - {item}")
    return report


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_cloud_preflight(args.strict, args.quiet, args.public_demo_env)
    return int(report.get("exit_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
