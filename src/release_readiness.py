from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Iterable

from src.data_contracts import validate_snapshot_directory


PUBLIC_FILES = (
    "README.md",
    "VALIDATION.md",
    "CHANGELOG.md",
    "ROADMAP.md",
    "PROJECT_BRIEF.md",
    "docs/ARCHITECTURE.md",
    "docs/DATA_FLOW.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/screenshots/SCREENSHOT_GUIDE.md",
    "docs/PUBLIC_REPO_SETTINGS.md",
    "docs/PUBLIC_RELEASE_AUDIT.md",
    "docs/PORTFOLIO_PRESENTATION.md",
    "docs/INTERVIEW_TALKING_POINTS.md",
    "docs/RESUME_SNIPPETS.md",
    "docs/OPERATIONS.md",
    "docs/assets/README.md",
    "docs/demo_briefs/README.md",
    "docs/demo_briefs/sample_observation_brief.md",
    "app.py",
)

PUBLIC_DIRS = (
    "src",
    "tools",
    "config",
    "sample_data",
)

REQUIRED_PUBLIC_ASSETS = (
    "README.md",
    "requirements.txt",
    ".streamlit/config.toml",
    ".streamlit/secrets.example.toml",
    "sample_data/ticks",
    "sample_data/fund_profiles/sample_fund_profiles.csv",
    "docs/demo_briefs/sample_observation_brief.md",
    "docs/screenshots/SCREENSHOT_GUIDE.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/ARCHITECTURE.md",
    "docs/DATA_FLOW.md",
    "docs/PUBLIC_REPO_SETTINGS.md",
    "docs/PUBLIC_RELEASE_AUDIT.md",
    "docs/PORTFOLIO_PRESENTATION.md",
    "docs/INTERVIEW_TALKING_POINTS.md",
    "docs/RESUME_SNIPPETS.md",
    "docs/OPERATIONS.md",
    "src/data_contracts.py",
    "tools/quality_gate.py",
    "LICENSE",
)

SAMPLE_NOTICE_TERMS = ("SAMPLE", "合成演示数据", "不代表真实行情", "不构成投资建议", "不预测未来走势")

_SLASH_USERS = "/" + "Users/"
_PROJECT_PARENT_HINT = "Desktop/" + "vibe coding"
LOCAL_PATH_PATTERNS = (
    (re.compile(re.escape(_SLASH_USERS) + r"[^\s)`'\"]+"), _SLASH_USERS),
    (re.compile(re.escape(_SLASH_USERS + "liujiayi")), _SLASH_USERS + "liujiayi"),
    (re.compile(re.escape(_PROJECT_PARENT_HINT)), _PROJECT_PARENT_HINT),
    (re.compile(r"/(?:Users|private|tmp|var|Volumes|home)/[^\s)`'\"]*fund-flow-monitor[^\s)`'\"]*"), "fund-flow-monitor absolute path"),
    (re.compile(r"[A-Za-z]:\\Users\\[^\s)`'\"]+"), "Windows user path"),
    (re.compile(r"/[^\s)`'\"]*\.venv/[^\s)`'\"]+"), ".venv absolute path"),
    (re.compile(r"/[^\s)`'\"]*site-packages/[^\s)`'\"]+"), "site-packages absolute path"),
)

SENSITIVE_PATTERNS = (
    (re.compile(r"AKShare\s+token", re.IGNORECASE), "AKShare token"),
    (re.compile(r"\bAPI\s*key\b", re.IGNORECASE), "API key"),
    (re.compile(r"\bsecret\b", re.IGNORECASE), "secret"),
    (re.compile(r"\bpassword\b", re.IGNORECASE), "password"),
    (re.compile(r"\bbearer\b", re.IGNORECASE), "bearer"),
    (re.compile(r"\bauthorization\b", re.IGNORECASE), "authorization"),
    (re.compile(r"student\s*ID", re.IGNORECASE), "student ID"),
    (re.compile(r"account\s+balance", re.IGNORECASE), "account balance"),
    (re.compile(r"real\s+holdings", re.IGNORECASE), "real holdings"),
    (re.compile(r"broker\s+account", re.IGNORECASE), "broker account"),
    (re.compile(r"真实账户"), "真实账户"),
    (re.compile(r"真实持仓"), "真实持仓"),
    (re.compile(r"券商账户"), "券商账户"),
    (re.compile(r"资金账号"), "资金账号"),
)

ALLOWED_SENSITIVE_CONTEXTS = (
    "不接真实账户",
    "不接入真实",
    "不读取真实",
    "不读取个人真实",
    "不读取任何真实",
    "不包含真实",
    "不代表真实",
    "不会读取真实",
    "不等同于真实",
    "不提交",
    "被忽略",
    "not read real",
    "does not read real",
    "not real holdings",
    "must not describe real holdings",
    "must not be described as real holdings",
    "no account connection",
    "does not connect",
    "Do not show",
    "No local path, secret",
    "Boundary Checks",
    "secrets.example",
    ".streamlit/secrets.toml",
    "secrets.toml",
    "secrets",
)

FORBIDDEN_INVESTMENT_PHRASES = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "抄底",
    "逃顶",
    "推荐买",
    "推荐卖",
    "建议买",
    "建议卖",
    "建仓",
    "清仓",
    "未来会涨",
    "未来会跌",
    "适合配置",
    "应该调仓",
    "趋势确立",
    "反转确认",
    "强烈看好",
    "明确机会",
    "建议关注",
)

ALLOWED_INVESTMENT_CONTEXTS = (
    "不构成投资建议",
    "不提供买卖建议",
    "不做买卖建议",
    "买卖建议或预测",
    "买卖建议或预测语气",
    "无买卖建议",
    "禁词",
    "禁止",
    "不允许",
    "must not include",
    "should not include",
    "action-oriented words",
    "FORBIDDEN",
    "FORBIDDEN_INVESTMENT_PHRASES",
)

REQUIRED_GITIGNORE_PATTERNS = (
    "data/ticks/*.csv",
    "data/warehouse/",
    "*.sqlite",
    "*.sqlite3",
    "*.db",
    ".env",
    ".venv/",
    ".streamlit/secrets.toml",
    "__pycache__/",
    ".pytest_cache/",
)

TEXT_SUFFIXES = {".md", ".py", ".json", ".toml", ".txt", ".csv"}

TRACKED_FORBIDDEN_PATTERNS = (
    re.compile(r"^\.env$"),
    re.compile(r"^\.venv/"),
    re.compile(r"^venv/"),
    re.compile(r"^env/"),
    re.compile(r"^\.streamlit/secrets\.toml$"),
    re.compile(r"^data/ticks/.+\.csv$"),
    re.compile(r"^data/warehouse/"),
    re.compile(r".*\.(sqlite|sqlite3|db)$"),
)

TRACKED_ALLOWED_PATHS = {
    ".env.example",
    "data/ticks/.gitkeep",
}

TRACKED_ALLOWED_PREFIXES = (
    "sample_data/ticks/",
)


def _root(project_root: str | Path = ".") -> Path:
    return Path(project_root).resolve()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _iter_text_files(project_root: Path, targets: dict | None = None) -> Iterable[Path]:
    target_info = targets or get_release_audit_targets(project_root)
    for rel in target_info.get("existing_files", []):
        path = project_root / rel
        if path.suffix in TEXT_SUFFIXES:
            yield path
    for rel in target_info.get("existing_dirs", []):
        directory = project_root / rel
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                yield path


def get_release_audit_targets(project_root: str | Path = ".") -> dict:
    root = _root(project_root)
    existing_files = []
    missing_files = []
    for rel in PUBLIC_FILES:
        if (root / rel).is_file():
            existing_files.append(rel)
        else:
            missing_files.append(rel)
    existing_dirs = []
    missing_dirs = []
    for rel in PUBLIC_DIRS:
        if (root / rel).is_dir():
            existing_dirs.append(rel)
        else:
            missing_dirs.append(rel)
    return {
        "existing_files": existing_files,
        "missing_files": missing_files,
        "existing_dirs": existing_dirs,
        "missing_dirs": missing_dirs,
    }


def scan_text_for_local_paths(text: str) -> list[str]:
    hits: list[str] = []
    for line in text.splitlines() or [text]:
        if "LOCAL_PATH_PATTERNS" in line or "re.compile" in line:
            continue
        for pattern, label in LOCAL_PATH_PATTERNS:
            if pattern.search(line):
                hits.append(label)
    return sorted(set(hits))


def scan_text_for_sensitive_terms(text: str) -> list[str]:
    hits: list[str] = []
    lines = text.splitlines() or [text]
    for line in lines:
        normalized = line.strip()
        if "SENSITIVE_PATTERNS" in normalized or "re.compile" in normalized:
            continue
        for pattern, label in SENSITIVE_PATTERNS:
            if not pattern.search(normalized):
                continue
            if any(allowed in normalized for allowed in ALLOWED_SENSITIVE_CONTEXTS):
                continue
            hits.append(label)
    return sorted(set(hits))


def scan_text_for_forbidden_investment_phrases(text: str) -> list[str]:
    hits: list[str] = []
    lines = text.splitlines() or [text]
    for line in lines:
        stripped = line.strip()
        if re.fullmatch(r"[\"'][^\"']+[\"'],?", stripped):
            continue
        if any(allowed in line for allowed in ALLOWED_INVESTMENT_CONTEXTS):
            continue
        for phrase in FORBIDDEN_INVESTMENT_PHRASES:
            if phrase in line:
                hits.append(phrase)
    return sorted(set(hits))


def scan_markdown_links(markdown_text: str, base_dir: str | Path) -> dict:
    base = Path(base_dir)
    raw_links = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", markdown_text)
    links_checked: list[str] = []
    existing_links: list[str] = []
    missing_links: list[str] = []
    external_links: list[str] = []
    anchor_links: list[str] = []
    for raw_link in raw_links:
        link = raw_link.strip()
        if not link:
            continue
        if link.startswith(("#", "mailto:")):
            anchor_links.append(link)
            continue
        if link.startswith(("http://", "https://", "data:", "app://")):
            external_links.append(link)
            continue
        path_part = link.split("#", 1)[0]
        if not path_part:
            anchor_links.append(link)
            continue
        links_checked.append(link)
        candidate = (base / path_part).resolve()
        if candidate.exists():
            existing_links.append(link)
        else:
            missing_links.append(link)
    return {
        "links_checked": links_checked,
        "existing_links": existing_links,
        "missing_links": missing_links,
        "external_links": external_links,
        "anchor_links": anchor_links,
    }


def check_required_public_assets(project_root: str | Path = ".") -> dict:
    root = _root(project_root)
    missing_assets: list[str] = []
    available_assets: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    for rel in REQUIRED_PUBLIC_ASSETS:
        path = root / rel
        if rel == "sample_data/ticks":
            ok = path.is_dir() and bool(list(path.glob("*.csv")))
        else:
            ok = path.exists()
        if ok:
            available_assets.append(rel)
        else:
            missing_assets.append(rel)
            errors.append(f"缺少公开展示资产：{rel}")
    label = "公开资产齐备" if not missing_assets else "公开资产缺失"
    return {
        "asset_label": label,
        "missing_assets": missing_assets,
        "available_assets": available_assets,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
    }


def check_sample_notice_coverage(project_root: str | Path = ".") -> dict:
    root = _root(project_root)
    files = (
        "README.md",
        "docs/demo_briefs/sample_observation_brief.md",
        "docs/screenshots/SCREENSHOT_GUIDE.md",
        "PROJECT_BRIEF.md",
    )
    file_results = {}
    missing_notice_files: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    for rel in files:
        path = root / rel
        text = _read_text(path) if path.exists() else ""
        missing_terms = [term for term in SAMPLE_NOTICE_TERMS if term not in text]
        file_results[rel] = {"exists": path.exists(), "missing_terms": missing_terms}
        if missing_terms:
            missing_notice_files.append(rel)
            warnings.append(f"{rel} 缺少 SAMPLE 边界说明：{', '.join(missing_terms)}")
    label = "SAMPLE 说明覆盖完整" if not missing_notice_files else "SAMPLE 说明需补充"
    return {
        "coverage_label": label,
        "file_results": file_results,
        "missing_notice_files": missing_notice_files,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
    }


def check_gitignore_safety(project_root: str | Path = ".") -> dict:
    root = _root(project_root)
    gitignore = root / ".gitignore"
    text = _read_text(gitignore) if gitignore.exists() else ""
    found = [pattern for pattern in REQUIRED_GITIGNORE_PATTERNS if pattern in text]
    missing = [pattern for pattern in REQUIRED_GITIGNORE_PATTERNS if pattern not in text]
    warnings: list[str] = []
    errors = [f".gitignore 缺少保护规则：{pattern}" for pattern in missing]
    label = "Git ignore 保护完整" if not missing else "Git ignore 保护需修复"
    return {
        "gitignore_label": label,
        "required_patterns_found": found,
        "required_patterns_missing": missing,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
    }


def check_sample_data_contract(project_root: str | Path = ".") -> dict:
    root = _root(project_root)
    report = validate_snapshot_directory(root / "sample_data/ticks", sample=True)
    errors = [f"SAMPLE 数据契约失败：{error}" for error in report.get("errors", [])]
    warnings = [f"SAMPLE 数据契约提示：{warning}" for warning in report.get("warnings", [])]
    label = "SAMPLE 数据契约通过" if not errors else "SAMPLE 数据契约需修复"
    return {
        "sample_data_contract_label": label,
        "contract_ok": not errors,
        "file_count": report.get("file_count", 0),
        "row_count": report.get("row_count", 0),
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
    }


def _parse_app_version(project_root: Path) -> str:
    config_text = _read_text(project_root / "src/config.py")
    match = re.search(r"APP_VERSION\s*=\s*[\"']([^\"']+)[\"']", config_text)
    return match.group(1).strip() if match else ""


def check_version_consistency(project_root: str | Path = ".") -> dict:
    root = _root(project_root)
    app_version = _parse_app_version(root)
    changelog_text = _read_text(root / "CHANGELOG.md")
    changelog_version_ok = bool(app_version and f"## {app_version}" in changelog_text)
    errors: list[str] = []
    warnings: list[str] = []
    if not app_version:
        errors.append("无法从 src/config.py 读取 APP_VERSION。")
    elif not changelog_version_ok:
        errors.append(f"CHANGELOG.md 缺少 {app_version} 发布记录。")
    label = "版本记录一致" if not errors else "版本记录需修复"
    return {
        "version_label": label,
        "app_version": app_version,
        "changelog_version_ok": changelog_version_ok,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
    }


def _is_forbidden_tracked_path(path: str) -> bool:
    if path in TRACKED_ALLOWED_PATHS:
        return False
    if any(path.startswith(prefix) for prefix in TRACKED_ALLOWED_PREFIXES):
        return False
    return any(pattern.search(path) for pattern in TRACKED_FORBIDDEN_PATTERNS)


def check_tracked_file_safety(project_root: str | Path = ".") -> dict:
    root = _root(project_root)
    warnings: list[str] = []
    errors: list[str] = []
    tracked_files: list[str] = []
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:  # pragma: no cover - defensive fallback for non-git environments
        warnings.append(f"无法运行 git ls-files：{exc}")
        return {
            "tracked_file_label": "无法检查 tracked files",
            "tracked_forbidden_files": [],
            "git_available": False,
            "warning_count": len(warnings),
            "error_count": len(errors),
            "warnings": warnings,
            "errors": errors,
        }
    if result.returncode != 0:
        warnings.append("当前目录可能不是 git 仓库，跳过 tracked files 检查。")
        return {
            "tracked_file_label": "无法检查 tracked files",
            "tracked_forbidden_files": [],
            "git_available": False,
            "warning_count": len(warnings),
            "error_count": len(errors),
            "warnings": warnings,
            "errors": errors,
        }
    tracked_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    forbidden_files = [path for path in tracked_files if _is_forbidden_tracked_path(path)]
    if forbidden_files:
        errors.extend(f"禁止提交的文件已被 git tracked：{path}" for path in forbidden_files)
    label = "tracked files 安全" if not forbidden_files else "tracked files 需修复"
    return {
        "tracked_file_label": label,
        "tracked_forbidden_files": forbidden_files,
        "git_available": True,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
    }


def _scan_project_text(project_root: Path, targets: dict) -> tuple[list[dict], list[dict], list[dict]]:
    local_hits: list[dict] = []
    sensitive_hits: list[dict] = []
    forbidden_hits: list[dict] = []
    for path in _iter_text_files(project_root, targets):
        rel = str(path.relative_to(project_root))
        text = _read_text(path)
        local = scan_text_for_local_paths(text)
        sensitive = scan_text_for_sensitive_terms(text)
        forbidden = scan_text_for_forbidden_investment_phrases(text)
        if local:
            local_hits.append({"file": rel, "hits": local})
        if sensitive:
            sensitive_hits.append({"file": rel, "hits": sensitive})
        if forbidden:
            forbidden_hits.append({"file": rel, "hits": forbidden})
    return local_hits, sensitive_hits, forbidden_hits


def _build_markdown_link_report(project_root: Path, targets: dict) -> dict:
    checked_files = []
    missing_links: list[dict] = []
    existing_count = 0
    external_count = 0
    anchor_count = 0
    for path in _iter_text_files(project_root, targets):
        if path.suffix != ".md":
            continue
        rel = str(path.relative_to(project_root))
        report = scan_markdown_links(_read_text(path), path.parent)
        checked_files.append(rel)
        existing_count += len(report["existing_links"])
        external_count += len(report["external_links"])
        anchor_count += len(report["anchor_links"])
        if report["missing_links"]:
            missing_links.append({"file": rel, "links": report["missing_links"]})
    return {
        "checked_files": checked_files,
        "missing_links": missing_links,
        "existing_link_count": existing_count,
        "external_link_count": external_count,
        "anchor_link_count": anchor_count,
        "missing_link_count": sum(len(item["links"]) for item in missing_links),
    }


def build_release_readiness_report(project_root: str | Path = ".") -> dict:
    root = _root(project_root)
    targets = get_release_audit_targets(root)
    public_assets = check_required_public_assets(root)
    sample_notice_coverage = check_sample_notice_coverage(root)
    gitignore_safety = check_gitignore_safety(root)
    sample_data_contract = check_sample_data_contract(root)
    version_consistency = check_version_consistency(root)
    tracked_file_safety = check_tracked_file_safety(root)
    markdown_link_report = _build_markdown_link_report(root, targets)
    local_path_hits, sensitive_hits, forbidden_phrase_hits = _scan_project_text(root, targets)

    warnings: list[str] = []
    errors: list[str] = []
    errors.extend(public_assets.get("errors", []))
    errors.extend(gitignore_safety.get("errors", []))
    errors.extend(sample_data_contract.get("errors", []))
    errors.extend(version_consistency.get("errors", []))
    errors.extend(tracked_file_safety.get("errors", []))
    warnings.extend(sample_notice_coverage.get("warnings", []))
    warnings.extend(sample_data_contract.get("warnings", []))
    warnings.extend(version_consistency.get("warnings", []))
    warnings.extend(tracked_file_safety.get("warnings", []))
    if targets.get("missing_files"):
        errors.extend(f"缺少审计目标文件：{path}" for path in targets["missing_files"])
    if targets.get("missing_dirs"):
        errors.extend(f"缺少审计目标目录：{path}" for path in targets["missing_dirs"])
    for item in markdown_link_report.get("missing_links", []):
        errors.append(f"{item['file']} 存在缺失链接：{', '.join(item['links'])}")
    for item in local_path_hits:
        errors.append(f"{item['file']} 存在本地路径风险：{', '.join(item['hits'])}")
    for item in forbidden_phrase_hits:
        errors.append(f"{item['file']} 存在动作性或预测性表达：{', '.join(item['hits'])}")
    for item in sensitive_hits:
        warnings.append(f"{item['file']} 存在需人工确认的敏感词：{', '.join(item['hits'])}")

    error_count = len(errors)
    warning_count = len(warnings)
    if error_count:
        label = "需要修复后再发布"
        reason = "存在缺失资产、断链、本地路径或越界表达。"
    elif warning_count:
        label = "存在轻微警告"
        reason = "核心发布检查通过，但仍有需人工确认的提示。"
    else:
        label = "发布检查通过"
        reason = "公开资产、SAMPLE 说明、gitignore、链接和发布文案检查通过。"
    return {
        "release_ready": error_count == 0,
        "readiness_label": label,
        "readiness_reason": reason,
        "target_summary": targets,
        "public_assets": public_assets,
        "sample_notice_coverage": sample_notice_coverage,
        "gitignore_safety": gitignore_safety,
        "sample_data_contract": sample_data_contract,
        "version_consistency": version_consistency,
        "tracked_file_safety": tracked_file_safety,
        "app_version": version_consistency.get("app_version", ""),
        "changelog_version_ok": version_consistency.get("changelog_version_ok", False),
        "tracked_forbidden_files": tracked_file_safety.get("tracked_forbidden_files", []),
        "markdown_link_report": markdown_link_report,
        "local_path_hits": local_path_hits,
        "sensitive_hits": sensitive_hits,
        "forbidden_phrase_hits": forbidden_phrase_hits,
        "warning_count": warning_count,
        "error_count": error_count,
        "warnings": warnings,
        "errors": errors,
    }


def render_release_readiness_markdown(report: dict) -> str:
    def _lines(items: list[str], empty: str) -> list[str]:
        return [f"- {item}" for item in items] if items else [f"- {empty}"]

    public_assets = report.get("public_assets", {})
    sample_notice = report.get("sample_notice_coverage", {})
    gitignore = report.get("gitignore_safety", {})
    sample_contract = report.get("sample_data_contract", {})
    version = report.get("version_consistency", {})
    tracked = report.get("tracked_file_safety", {})
    links = report.get("markdown_link_report", {})
    lines = [
        "# Release Readiness Report",
        "",
        "## Summary",
        "",
        f"- 状态：{report.get('readiness_label', '--')}",
        f"- 说明：{report.get('readiness_reason', '')}",
        f"- warning_count：{report.get('warning_count', 0)}",
        f"- error_count：{report.get('error_count', 0)}",
        "",
        "## Public Assets",
        "",
        f"- 状态：{public_assets.get('asset_label', '--')}",
        f"- 可用资产数量：{len(public_assets.get('available_assets', []))}",
        f"- 缺失资产数量：{len(public_assets.get('missing_assets', []))}",
        "",
        "## SAMPLE Notice Coverage",
        "",
        f"- 状态：{sample_notice.get('coverage_label', '--')}",
        f"- 需补充文件数量：{len(sample_notice.get('missing_notice_files', []))}",
        "",
        "## Git Ignore Safety",
        "",
        f"- 状态：{gitignore.get('gitignore_label', '--')}",
        f"- 已覆盖规则数量：{len(gitignore.get('required_patterns_found', []))}",
        f"- 缺失规则数量：{len(gitignore.get('required_patterns_missing', []))}",
        "",
        "## SAMPLE Data Contract",
        "",
        f"- 状态：{sample_contract.get('sample_data_contract_label', '--')}",
        f"- SAMPLE 文件数量：{sample_contract.get('file_count', 0)}",
        f"- SAMPLE 行数：{sample_contract.get('row_count', 0)}",
        "",
        "## Version / Tracked Files",
        "",
        f"- APP_VERSION：{version.get('app_version', '--')}",
        f"- CHANGELOG 对应版本：{version.get('changelog_version_ok', False)}",
        f"- tracked forbidden files：{len(tracked.get('tracked_forbidden_files', []))}",
        "",
        "## Markdown Links",
        "",
        f"- 检查 Markdown 文件数量：{len(links.get('checked_files', []))}",
        f"- 缺失链接数量：{links.get('missing_link_count', 0)}",
        f"- 外部链接数量：{links.get('external_link_count', 0)}",
        "",
        "## Local Path / Sensitive Text Scan",
        "",
        f"- 本地路径风险文件数量：{len(report.get('local_path_hits', []))}",
        f"- 需人工确认敏感词文件数量：{len(report.get('sensitive_hits', []))}",
        "",
        "## Forbidden Phrase Scan",
        "",
        f"- 越界表达文件数量：{len(report.get('forbidden_phrase_hits', []))}",
        "",
        "## Next Manual Checks",
        "",
        "- 打开 Streamlit app，使用 SAMPLE + 作品集演示模式浏览核心页面。",
        "- 检查 demo brief 与观察简报是否明确说明 SAMPLE 合成演示数据。",
        "- 运行 git status，确认真实 CSV、SQLite、secrets 和虚拟环境未进入提交。",
        "- 如需提交报告，确认本报告不包含本地绝对路径或敏感信息。",
        "",
        "## Warnings",
        "",
        *_lines(report.get("warnings", []), "无警告。"),
        "",
        "## Errors",
        "",
        *_lines(report.get("errors", []), "无错误。"),
    ]
    return "\n".join(lines) + "\n"


def validate_release_readiness_text(text: str) -> list[str]:
    hits = []
    hits.extend(scan_text_for_local_paths(text))
    hits.extend(scan_text_for_forbidden_investment_phrases(text))
    return sorted(set(hits))
