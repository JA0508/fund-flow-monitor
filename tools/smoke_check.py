from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.fund_profiles import get_funds, load_fund_profiles, validate_fund_profile  # noqa: E402
from src.snapshot_catalog import build_snapshot_catalog, get_latest_snapshot_date  # noqa: E402
from src.watchlist import get_watchlist_themes, load_watchlist  # noqa: E402


REQUIRED_IMPORTS = ("streamlit", "pandas", "plotly", "akshare")
REQUIRED_FILES = (
    "app.py",
    "src/theme_pool.py",
    "src/theme_radar.py",
    "src/concept_flow.py",
    "src/theme_concepts.py",
    "src/fund_profiles.py",
    "src/intraday_hotspots.py",
    "src/snapshot_catalog.py",
    "src/watchlist.py",
    "config/watchlist.json",
    "config/fund_profiles.json",
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


def build_smoke_report(project_root: Path = PROJECT_ROOT) -> dict:
    latest_csv = find_latest_csv(project_root / "data/ticks")
    catalog = build_snapshot_catalog(str(project_root / "data/ticks"))
    return {
        "project_root": str(project_root),
        "python": check_python_version(),
        "imports": check_imports(),
        "files": check_project_files(project_root),
        "watchlist": load_watchlist_status(project_root / "config/watchlist.json"),
        "fund_profiles": load_fund_profile_status(project_root / "config/fund_profiles.json"),
        "csv": summarize_csv(latest_csv),
        "snapshot_catalog": {
            "date_count": int(len(catalog)),
            "latest_snapshot_date": get_latest_snapshot_date(catalog) or "<none>",
        },
    }


def main() -> int:
    report = build_smoke_report()
    print("Fund Flow Monitor v1.0 本地冒烟检查")
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

    csv = report["csv"]
    print(f"CSV 数据文件存在: {csv['exists']}")
    print(f"CSV 文件路径: {csv['path'] or '<none>'}")
    print(f"CSV 行数: {csv['rows']}")
    print(f"captured_time 数量: {csv['captured_time_count']}")
    print(f"最新 captured_time: {csv['latest_captured_time']}")
    catalog = report["snapshot_catalog"]
    print(f"CSV 快照日期数量: {catalog['date_count']}")
    print(f"最新快照日期: {catalog['latest_snapshot_date']}")

    ok = (
        py["ok"]
        and all(report["imports"].values())
        and all(report["files"].values())
        and watchlist["ok"]
        and fund_profiles["ok"]
    )
    print(f"检查结果: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
