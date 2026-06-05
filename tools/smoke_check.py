from __future__ import annotations

import importlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.fund_profiles import get_funds, load_fund_profiles, validate_fund_profile  # noqa: E402
from src.fund_profile_importer import (  # noqa: E402
    build_profile_theme_exposure_table,
    load_fund_profiles_csv,
    validate_fund_profiles_csv,
)
from src import insight_brief  # noqa: E402
from src.brief_templates import (  # noqa: E402
    get_brief_template_modes,
    validate_brief_template_text,
)
from src.local_warehouse import (  # noqa: E402
    audit_warehouse,
    connect_warehouse,
    initialize_warehouse,
    query_warehouse_summary,
    rebuild_warehouse_from_csv_directory,
    summarize_warehouse_status,
    validate_warehouse_text,
)
from src.warehouse_explorer import (  # noqa: E402
    build_csv_warehouse_consistency_report,
    build_warehouse_explorer_summary,
    get_warehouse_date_overview,
    get_warehouse_source_type_summary,
    summarize_csv_warehouse_consistency,
    validate_warehouse_explorer_text,
)
from src.presentation import (  # noqa: E402
    build_status_badge_config,
    get_display_mode_options,
    validate_presentation_text,
)
from src.sample_data import build_sample_snapshot_catalog, get_latest_sample_date  # noqa: E402
from src.snapshot_catalog import build_snapshot_catalog, get_latest_snapshot_date  # noqa: E402
from src.snapshot_quality import build_snapshot_quality_report  # noqa: E402
from src.theme_taxonomy import get_theme_names, load_theme_taxonomy, validate_theme_taxonomy  # noqa: E402
from src.watchlist import get_watchlist_themes, load_watchlist  # noqa: E402
from tools.rebuild_local_warehouse import rebuild_local_warehouse as run_rebuild_local_warehouse  # noqa: E402


REQUIRED_IMPORTS = ("streamlit", "pandas", "plotly", "akshare", "numpy")
REQUIRED_FILES = (
    "app.py",
    "requirements.txt",
    ".streamlit/config.toml",
    ".streamlit/secrets.example.toml",
    "src/theme_pool.py",
    "src/theme_radar.py",
    "src/concept_flow.py",
    "src/theme_concepts.py",
    "src/theme_coverage.py",
    "src/theme_taxonomy.py",
    "src/fund_profiles.py",
    "src/fund_profile_importer.py",
    "src/insight_brief.py",
    "src/intraday_hotspots.py",
    "src/multi_day_trends.py",
    "src/snapshot_catalog.py",
    "src/sample_data.py",
    "src/snapshot_quality.py",
    "src/presentation.py",
    "src/brief_templates.py",
    "src/local_warehouse.py",
    "src/warehouse_explorer.py",
    "src/watchlist.py",
    "tools/generate_sample_data.py",
    "tools/collect_market_snapshot.py",
    "tools/export_sample_brief.py",
    "tools/rebuild_local_warehouse.py",
    "config/watchlist.json",
    "config/fund_profiles.json",
    "config/theme_taxonomy.json",
    "sample_data/ticks/sector_flow_2026-01-15.csv",
    "sample_data/ticks/sector_flow_2026-01-16.csv",
    "sample_data/fund_profiles/sample_fund_profiles.csv",
    "docs/screenshots/SCREENSHOT_GUIDE.md",
    "docs/demo_briefs/README.md",
    "docs/demo_briefs/sample_observation_brief.md",
    "docs/RELEASE_CHECKLIST.md",
    "README.md",
)


def check_python_version(min_version: tuple[int, int] = (3, 10)) -> dict:
    current = sys.version_info
    return {
        "version": f"{current.major}.{current.minor}.{current.micro}",
        "ok": (current.major, current.minor) >= min_version,
        "required": f"{min_version[0]}.{min_version[1]}+",
    }


def check_imports(modules: tuple[str, ...] = REQUIRED_IMPORTS) -> dict[str, bool]:
    results = {}
    for module in modules:
        try:
            importlib.import_module(module)
            results[module] = True
        except ImportError:
            results[module] = False
    return results


def check_project_files(project_root: Path = PROJECT_ROOT) -> dict[str, bool]:
    return {path: (project_root / path).exists() for path in REQUIRED_FILES}


def load_watchlist_status(path: str | Path = PROJECT_ROOT / "config/watchlist.json") -> dict:
    watchlist = load_watchlist(str(path))
    themes = get_watchlist_themes(watchlist)
    return {
        "watchlist_name": watchlist.get("watchlist_name", ""),
        "themes": themes,
        "theme_count": len(themes),
        "ok": bool(themes),
    }


def load_fund_profile_status(path: str | Path = PROJECT_ROOT / "config/fund_profiles.json") -> dict:
    profile = load_fund_profiles(str(path))
    funds = get_funds(profile)
    warnings = validate_fund_profile(profile)
    return {
        "profile_name": profile.get("profile_name", ""),
        "fund_count": len(funds),
        "warning_count": len(warnings),
        "ok": bool(funds),
    }


def load_taxonomy_status(path: str | Path = PROJECT_ROOT / "config/theme_taxonomy.json") -> dict:
    taxonomy = load_theme_taxonomy(str(path))
    warnings = validate_theme_taxonomy(taxonomy)
    names = get_theme_names(taxonomy)
    return {
        "taxonomy_name": taxonomy.get("taxonomy_name", ""),
        "theme_count": len(names),
        "warning_count": len(warnings),
        "ok": bool(names),
    }


def find_latest_csv(data_dir: Path = PROJECT_ROOT / "data/ticks") -> Path | None:
    files = sorted(data_dir.glob("sector_flow_*.csv"))
    return files[-1] if files else None


def summarize_csv(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {
            "exists": False,
            "path": None,
            "rows": 0,
            "captured_time_count": 0,
            "latest_captured_time": "<none>",
        }
    df = pd.read_csv(path)
    latest_time = "<none>"
    captured_count = 0
    if "captured_time" in df.columns and not df.empty:
        captured_count = int(df["captured_time"].nunique())
        latest_time = str(df["captured_time"].dropna().iloc[-1])
    return {
        "exists": True,
        "path": str(path),
        "rows": int(len(df)),
        "captured_time_count": captured_count,
        "latest_captured_time": latest_time,
    }


def _git_check_ignore(path: str, project_root: Path = PROJECT_ROOT) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", path],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def check_warehouse_status(project_root: Path = PROJECT_ROOT) -> dict:
    with tempfile.TemporaryDirectory() as tmp_dir:
        warehouse_path = Path(tmp_dir) / "fund_flow.sqlite"
        dry_run = run_rebuild_local_warehouse(
            warehouse_path=str(Path(tmp_dir) / "dry_run.sqlite"),
            sample_dir=str(project_root / "sample_data/ticks"),
            include_local=False,
            include_sample=True,
            dry_run=True,
            quiet=True,
        )
        conn = connect_warehouse(str(warehouse_path))
        try:
            initialize_warehouse(conn)
            rebuild = rebuild_warehouse_from_csv_directory(
                conn,
                str(project_root / "sample_data/ticks"),
                "SAMPLE",
                clear_source=True,
            )
            summary = query_warehouse_summary(conn)
            audit = audit_warehouse(conn)
            forbidden_hits = validate_warehouse_text(summarize_warehouse_status(summary, audit))
            explorer_summary = build_warehouse_explorer_summary(conn)
            source_summary_df = get_warehouse_source_type_summary(conn)
            date_overview_df = get_warehouse_date_overview(conn)
            consistency = build_csv_warehouse_consistency_report(
                conn,
                local_csv_dir=str(project_root / "data/ticks"),
                sample_csv_dir=str(project_root / "sample_data/ticks"),
            )
            explorer_forbidden_hits = validate_warehouse_explorer_text(summarize_csv_warehouse_consistency(consistency))
        finally:
            conn.close()
    return {
        "warehouse_module_imported": True,
        "warehouse_schema_initialized": True,
        "warehouse_explorer_imported": True,
        "explorer_summary_available": bool(explorer_summary.get("explorer_available")),
        "explorer_source_type_count": int(source_summary_df["source_type"].nunique()) if not source_summary_df.empty else 0,
        "explorer_date_count": int(date_overview_df["data_date"].nunique()) if not date_overview_df.empty else 0,
        "csv_warehouse_consistency_label": consistency.get("overall_label"),
        "sample_rebuild_dry_run_label": dry_run.get("summary_label"),
        "sample_rebuild_temp_label": rebuild.get("rebuild_label"),
        "sample_inserted_rows": int(rebuild.get("inserted_rows", 0) or 0),
        "warehouse_gitignore_ok": _git_check_ignore("data/warehouse/fund_flow.sqlite", project_root),
        "warehouse_text_forbidden_hits": forbidden_hits,
        "warehouse_explorer_forbidden_hits": explorer_forbidden_hits,
    }


def build_smoke_report(project_root: Path = PROJECT_ROOT) -> dict:
    latest_csv = find_latest_csv(project_root / "data/ticks")
    catalog = build_snapshot_catalog(str(project_root / "data/ticks"))
    sample_catalog = build_sample_snapshot_catalog(str(project_root / "sample_data/ticks"))
    sample_profile_csv = load_fund_profiles_csv(str(project_root / "sample_data/fund_profiles/sample_fund_profiles.csv"))
    sample_profile_validation = validate_fund_profiles_csv(sample_profile_csv, load_theme_taxonomy(str(project_root / "config/theme_taxonomy.json")))
    sample_profile_exposure = build_profile_theme_exposure_table(sample_profile_csv, load_theme_taxonomy(str(project_root / "config/theme_taxonomy.json")))
    snapshot_quality = build_snapshot_quality_report(
        directory=str(project_root / "data/ticks"),
        sample_directory=str(project_root / "sample_data/ticks"),
    )
    warehouse_status = check_warehouse_status(project_root)
    presentation_statuses = ["LIVE", "CACHE", "HISTORY", "SAMPLE", "DEMO", "EMPTY"]
    status_badges = [build_status_badge_config(status) for status in presentation_statuses]
    readme_path = project_root / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
    demo_brief_path = project_root / "docs/demo_briefs/sample_observation_brief.md"
    demo_brief_text = demo_brief_path.read_text(encoding="utf-8") if demo_brief_path.exists() else ""
    presentation_text = " ".join(
        get_display_mode_options()
        + [str(item.get("label", "")) for item in status_badges]
        + [str(item.get("description", "")) for item in status_badges]
    )
    return {
        "project_root": str(project_root),
        "python": check_python_version(),
        "imports": check_imports(),
        "files": check_project_files(project_root),
        "watchlist": load_watchlist_status(project_root / "config/watchlist.json"),
        "fund_profiles": load_fund_profile_status(project_root / "config/fund_profiles.json"),
        "taxonomy": load_taxonomy_status(project_root / "config/theme_taxonomy.json"),
        "insight_brief_import": bool(insight_brief),
        "csv": summarize_csv(latest_csv),
        "snapshot_catalog": {
            "date_count": int(len(catalog)),
            "latest_snapshot_date": get_latest_snapshot_date(catalog) or "<none>",
        },
        "sample_catalog": {
            "date_count": int(len(sample_catalog)),
            "latest_sample_date": get_latest_sample_date(sample_catalog) or "<none>",
        },
        "sample_profile_csv": {
            "row_count": int(sample_profile_validation.get("row_count", 0)),
            "profile_count": int(sample_profile_validation.get("profile_count", 0)),
            "validation_label": sample_profile_validation.get("validation_label", "--"),
            "warning_count": int(sample_profile_validation.get("warning_count", 0)),
            "error_count": int(sample_profile_validation.get("error_count", 0)),
            "exposure_rows": int(len(sample_profile_exposure)),
        },
        "snapshot_quality": {
            "local_file_count": int(snapshot_quality.get("local_file_count", 0) or 0),
            "sample_file_count": int(snapshot_quality.get("sample_file_count", 0) or 0),
            "report_label": snapshot_quality.get("report_label", "--"),
            "local_warning_count": int(snapshot_quality.get("local_warning_count", 0) or 0),
            "local_error_count": int(snapshot_quality.get("local_error_count", 0) or 0),
            "sample_warning_count": int(snapshot_quality.get("sample_warning_count", 0) or 0),
            "sample_error_count": int(snapshot_quality.get("sample_error_count", 0) or 0),
        },
        "warehouse": warehouse_status,
        "presentation": {
            "display_mode_count": len(get_display_mode_options()),
            "supported_status_count": sum(1 for item in status_badges if item.get("status") in presentation_statuses),
            "screenshot_guide_exists": (project_root / "docs/screenshots/SCREENSHOT_GUIDE.md").exists(),
            "readme_has_demo_walkthrough": "Demo Walkthrough" in readme_text,
            "readme_has_portfolio_mode": "Portfolio Presentation Mode" in readme_text or "作品集演示模式" in readme_text,
            "presentation_text_forbidden_hits": validate_presentation_text(presentation_text),
        },
        "brief_templates": {
            "brief_template_mode_count": len(get_brief_template_modes()),
            "demo_brief_exists": demo_brief_path.exists(),
            "demo_brief_has_sample_notice": ("SAMPLE" in demo_brief_text and "合成演示数据" in demo_brief_text),
            "demo_brief_forbidden_hits": validate_brief_template_text(demo_brief_text),
            "release_checklist_exists": (project_root / "docs/RELEASE_CHECKLIST.md").exists(),
        },
    }


def main() -> int:
    report = build_smoke_report()
    print("Fund Flow Monitor v2.1 本地冒烟检查")
    print(f"项目路径: {report['project_root']}")
    py = report["python"]
    print(f"Python 版本: {py['version']} (要求 {py['required']}) -> {'OK' if py['ok'] else 'FAIL'}")

    print("关键依赖 import:")
    for name, ok in report["imports"].items():
        print(f"  {name}: {'OK' if ok else 'MISSING'}")

    print("关键文件:")
    for path, ok in report["files"].items():
        print(f"  {path}: {'OK' if ok else 'MISSING'}")

    watchlist = report["watchlist"]
    print(f"watchlist: {watchlist['watchlist_name']} -> {watchlist['theme_count']} 个主题")
    print(f"watchlist themes: {watchlist['themes']}")
    fund_profiles = report["fund_profiles"]
    print(
        f"fund profiles: {fund_profiles['profile_name']} -> "
        f"{fund_profiles['fund_count']} 只基金/ETF, warnings={fund_profiles['warning_count']}"
    )
    taxonomy = report["taxonomy"]
    print(
        f"theme taxonomy: {taxonomy['taxonomy_name']} -> "
        f"{taxonomy['theme_count']} 个主题, warnings={taxonomy['warning_count']}"
    )
    print(f"insight_brief import: {'OK' if report['insight_brief_import'] else 'FAIL'}")

    csv = report["csv"]
    print(f"CSV 数据文件存在: {csv['exists']}")
    print(f"CSV 文件路径: {csv['path'] or '<none>'}")
    print(f"CSV 行数: {csv['rows']}")
    print(f"captured_time 数量: {csv['captured_time_count']}")
    print(f"最新 captured_time: {csv['latest_captured_time']}")
    catalog = report["snapshot_catalog"]
    print(f"CSV 快照日期数量: {catalog['date_count']}")
    print(f"最新快照日期: {catalog['latest_snapshot_date']}")
    sample_catalog = report["sample_catalog"]
    print(f"SAMPLE 样例日期数量: {sample_catalog['date_count']}")
    print(f"最新 SAMPLE 日期: {sample_catalog['latest_sample_date']}")
    sample_profile = report["sample_profile_csv"]
    print(f"SAMPLE fund profile CSV 行数: {sample_profile['row_count']}")
    print(f"SAMPLE fund profile 数量: {sample_profile['profile_count']}")
    print(f"SAMPLE fund profile validation: {sample_profile['validation_label']}")
    print(f"SAMPLE fund profile warnings/errors: {sample_profile['warning_count']} / {sample_profile['error_count']}")
    snapshot_quality = report["snapshot_quality"]
    print(f"snapshot quality report: {snapshot_quality['report_label']}")
    print(f"snapshot quality local files: {snapshot_quality['local_file_count']}")
    print(f"snapshot quality sample files: {snapshot_quality['sample_file_count']}")
    print(
        "snapshot quality warnings/errors: "
        f"local {snapshot_quality['local_warning_count']}/{snapshot_quality['local_error_count']} | "
        f"sample {snapshot_quality['sample_warning_count']}/{snapshot_quality['sample_error_count']}"
    )
    warehouse = report["warehouse"]
    print(f"warehouse module imported: {warehouse['warehouse_module_imported']}")
    print(f"warehouse schema initialized: {warehouse['warehouse_schema_initialized']}")
    print(f"warehouse explorer imported: {warehouse['warehouse_explorer_imported']}")
    print(f"warehouse explorer available: {warehouse['explorer_summary_available']}")
    print(f"warehouse explorer source/date count: {warehouse['explorer_source_type_count']} / {warehouse['explorer_date_count']}")
    print(f"CSV-Warehouse consistency: {warehouse['csv_warehouse_consistency_label']}")
    print(f"warehouse sample rebuild dry-run label: {warehouse['sample_rebuild_dry_run_label']}")
    print(f"warehouse sample rebuild temp label: {warehouse['sample_rebuild_temp_label']}")
    print(f"warehouse sample inserted rows: {warehouse['sample_inserted_rows']}")
    print(f"warehouse gitignore ok: {warehouse['warehouse_gitignore_ok']}")
    print(f"warehouse text forbidden hits: {warehouse['warehouse_text_forbidden_hits']}")
    print(f"warehouse explorer forbidden hits: {warehouse['warehouse_explorer_forbidden_hits']}")
    presentation = report["presentation"]
    print(f"display mode count: {presentation['display_mode_count']}")
    print(f"status badge supported count: {presentation['supported_status_count']}")
    print(f"screenshot guide exists: {presentation['screenshot_guide_exists']}")
    print(f"README has Demo Walkthrough: {presentation['readme_has_demo_walkthrough']}")
    print(f"README has Portfolio Presentation Mode: {presentation['readme_has_portfolio_mode']}")
    print(f"presentation text forbidden hits: {presentation['presentation_text_forbidden_hits']}")
    brief_templates = report["brief_templates"]
    print(f"brief template mode count: {brief_templates['brief_template_mode_count']}")
    print(f"demo brief exists: {brief_templates['demo_brief_exists']}")
    print(f"demo brief has SAMPLE notice: {brief_templates['demo_brief_has_sample_notice']}")
    print(f"demo brief forbidden hits: {brief_templates['demo_brief_forbidden_hits']}")
    print(f"release checklist exists: {brief_templates['release_checklist_exists']}")

    ok = (
        py["ok"]
        and all(report["imports"].values())
        and all(report["files"].values())
        and watchlist["ok"]
        and fund_profiles["ok"]
        and taxonomy["ok"]
        and report["insight_brief_import"]
        and sample_catalog["date_count"] >= 2
        and sample_profile["profile_count"] >= 5
        and sample_profile["error_count"] == 0
        and snapshot_quality["sample_file_count"] >= 1
        and warehouse["warehouse_module_imported"]
        and warehouse["warehouse_schema_initialized"]
        and warehouse["warehouse_explorer_imported"]
        and warehouse["explorer_summary_available"]
        and warehouse["sample_inserted_rows"] > 0
        and warehouse["warehouse_gitignore_ok"]
        and not warehouse["warehouse_text_forbidden_hits"]
        and not warehouse["warehouse_explorer_forbidden_hits"]
        and presentation["display_mode_count"] == 2
        and presentation["supported_status_count"] == 6
        and presentation["screenshot_guide_exists"]
        and presentation["readme_has_demo_walkthrough"]
        and presentation["readme_has_portfolio_mode"]
        and not presentation["presentation_text_forbidden_hits"]
        and brief_templates["brief_template_mode_count"] == 2
        and brief_templates["demo_brief_exists"]
        and brief_templates["demo_brief_has_sample_notice"]
        and not brief_templates["demo_brief_forbidden_hits"]
        and brief_templates["release_checklist_exists"]
    )
    print(f"检查结果: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
