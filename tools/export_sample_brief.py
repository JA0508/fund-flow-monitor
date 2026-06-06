from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.brief_templates import (  # noqa: E402
    PORTFOLIO_BRIEF_MODE,
    STANDARD_BRIEF_MODE,
    build_brief_compliance_report,
    build_brief_metadata,
    render_brief_markdown_with_extra_sections,
    validate_brief_markdown_structure,
)
from src.config import APP_VERSION  # noqa: E402
from src.fund_profiles import (  # noqa: E402
    build_fund_summary,
    build_fund_theme_exposure,
    build_holding_related_pool,
    get_funds,
    load_fund_profiles,
)
from src.insight_brief import (  # noqa: E402
    build_data_context_summary,
    build_observation_brief,
    summarize_holding_pool_for_brief,
    summarize_intraday_for_brief,
    summarize_multi_day_for_brief,
    summarize_taxonomy_coverage_for_brief,
    summarize_theme_radar_for_brief,
)
from src.intraday_hotspots import (  # noqa: E402
    build_intraday_hotspot_pool,
    build_intraday_hotspot_summary,
    build_theme_intraday_history,
    calculate_intraday_theme_metrics,
)
from src.multi_day_trends import (  # noqa: E402
    build_daily_theme_snapshots,
    build_multi_day_trend_pool,
    build_multi_day_trend_summary,
    calculate_multi_day_theme_metrics,
)
from src.local_warehouse import (  # noqa: E402
    connect_warehouse,
    initialize_warehouse,
    rebuild_warehouse_from_csv_directory,
    safe_close_connection,
)
from src.sample_data import build_sample_snapshot_catalog, get_latest_sample_date, load_sample_snapshot_by_date  # noqa: E402
from src.snapshot_catalog import get_snapshot_summary  # noqa: E402
from src.theme_history import (  # noqa: E402
    build_theme_history_from_sector_history,
    build_theme_history_quality_report,
    load_sector_history_from_warehouse,
    summarize_theme_history,
)
from src.theme_history_brief import (  # noqa: E402
    build_theme_history_brief_compliance_report,
    build_theme_history_brief_context,
    render_theme_history_brief_section,
)
from src.theme_history_viz import build_theme_history_visual_summary  # noqa: E402
from src.theme_coverage import build_theme_coverage_report  # noqa: E402
from src.theme_pool import build_theme_snapshot  # noqa: E402
from src.theme_radar import build_theme_radar_snapshot  # noqa: E402
from src.theme_taxonomy import load_theme_taxonomy  # noqa: E402


DEFAULT_OUTPUT = "docs/demo_briefs/sample_observation_brief.md"
DEFAULT_SAMPLE_DIR = "sample_data/ticks"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="导出 SAMPLE 合成演示数据观察简报。")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Markdown 输出路径。")
    parser.add_argument(
        "--template",
        default="portfolio",
        choices=("portfolio", "standard"),
        help="导出模板：portfolio=作品集演示简报，standard=标准简报。",
    )
    parser.add_argument("--sample-dir", default=DEFAULT_SAMPLE_DIR, help="SAMPLE 快照目录。")
    parser.add_argument(
        "--include-theme-history",
        dest="include_theme_history",
        action="store_true",
        default=True,
        help="在 demo brief 中加入 SAMPLE 主题历史观察摘要。",
    )
    parser.add_argument(
        "--no-theme-history",
        dest="include_theme_history",
        action="store_false",
        help="不加入主题历史观察摘要。",
    )
    parser.add_argument("--theme-mode", default="代表口径", help="主题历史摘要使用的主题口径。")
    parser.add_argument("--quiet", action="store_true", help="减少命令行输出。")
    return parser


def _resolve_path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _latest_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    if "captured_at" in work.columns:
        work["captured_at"] = pd.to_datetime(work["captured_at"], errors="coerce")
        valid = work.dropna(subset=["captured_at"])
        if not valid.empty:
            return valid[valid["captured_at"].eq(valid["captured_at"].max())].copy()
    if "captured_time" in work.columns and not work["captured_time"].dropna().empty:
        latest_time = str(work["captured_time"].dropna().astype(str).max())
        return work[work["captured_time"].astype(str).eq(latest_time)].copy()
    return work.copy()


def _industry_latest(ticks: pd.DataFrame) -> pd.DataFrame:
    if ticks is None or ticks.empty:
        return pd.DataFrame()
    if "sector_type" in ticks.columns:
        ticks = ticks[ticks["sector_type"].eq("行业资金流")].copy()
    return _latest_snapshot(ticks)


def _build_sample_observation_brief(sample_dir: Path) -> tuple[dict, dict, str, dict]:
    sample_catalog = build_sample_snapshot_catalog(str(sample_dir))
    latest_sample_date = get_latest_sample_date(sample_catalog)
    if sample_catalog.empty or not latest_sample_date:
        raise RuntimeError("暂无 SAMPLE 快照数据，可先运行 python tools/generate_sample_data.py。")

    sample_ticks = load_sample_snapshot_by_date(latest_sample_date, str(sample_dir))
    sample_summary = get_snapshot_summary(sample_ticks)
    latest_industry = _industry_latest(sample_ticks)
    if latest_industry.empty:
        raise RuntimeError("SAMPLE 快照缺少行业资金流最新帧，无法生成主题观察简报。")

    theme_snapshot = build_theme_snapshot(latest_industry, theme_mode="strict_representative")
    radar = build_theme_radar_snapshot(theme_snapshot)

    intraday_history = build_theme_intraday_history(sample_ticks, mode="strict_representative")
    intraday_metrics = calculate_intraday_theme_metrics(intraday_history)
    intraday_pool = build_intraday_hotspot_pool(intraday_metrics, top_n=12)
    intraday_summary = build_intraday_hotspot_summary(intraday_pool)

    daily_theme = build_daily_theme_snapshots(sample_catalog, data_dir=str(sample_dir), mode="strict_representative")
    multi_day_metrics = calculate_multi_day_theme_metrics(daily_theme)
    multi_day_pool = build_multi_day_trend_pool(multi_day_metrics, top_n=12)
    multi_day_summary = build_multi_day_trend_summary(multi_day_pool)

    fund_profile = load_fund_profiles()
    exposure = build_fund_theme_exposure(get_funds(fund_profile))
    holding_pool = build_holding_related_pool(exposure, radar)
    fund_summary = build_fund_summary(holding_pool)

    taxonomy = load_theme_taxonomy()
    coverage_report = build_theme_coverage_report(latest_industry, taxonomy)

    data_context = build_data_context_summary(
        latest_sample_date,
        "SAMPLE",
        sample_summary,
        "严格代表口径",
    )
    brief = build_observation_brief(
        data_context,
        summarize_theme_radar_for_brief(radar),
        summarize_intraday_for_brief(intraday_summary, intraday_pool),
        summarize_multi_day_for_brief(multi_day_summary, multi_day_pool),
        summarize_holding_pool_for_brief(fund_summary),
        summarize_taxonomy_coverage_for_brief(coverage_report, {}),
    )
    metadata = build_brief_metadata(
        latest_sample_date,
        "SAMPLE",
        "严格代表口径",
        APP_VERSION,
        "sample_data/ticks",
    )
    return brief, metadata, latest_sample_date, sample_summary


def _build_sample_theme_history_section(sample_dir: Path, theme_mode: str = "代表口径") -> tuple[str, dict]:
    with tempfile.TemporaryDirectory(prefix="yangjibao_sample_warehouse_") as tmp_dir:
        warehouse_path = Path(tmp_dir) / "sample_theme_history.sqlite"
        conn = connect_warehouse(str(warehouse_path))
        try:
            initialize_warehouse(conn)
            rebuild = rebuild_warehouse_from_csv_directory(
                conn,
                str(sample_dir),
                source_type="SAMPLE",
                clear_source=True,
            )
            if rebuild.get("error_count"):
                context = build_theme_history_brief_context(
                    {
                        "history_available": False,
                        "summary_label": "主题历史暂不可用",
                        "summary_reason": "SAMPLE 主题历史构建时出现可读错误，未生成历史结论。",
                    },
                    source_type="SAMPLE",
                    theme_mode=theme_mode,
                )
                section = render_theme_history_brief_section(context)
                return section, build_theme_history_brief_compliance_report(section)
            sector_history = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=True)
            taxonomy = load_theme_taxonomy()
            theme_history = build_theme_history_from_sector_history(sector_history, taxonomy, theme_mode=theme_mode)
            summary = summarize_theme_history(theme_history, top_n=5)
            quality = build_theme_history_quality_report(sector_history, theme_history)
            visual = build_theme_history_visual_summary(theme_history, top_n=5)
            context = build_theme_history_brief_context(
                summary,
                quality,
                visual,
                source_type="SAMPLE",
                theme_mode=theme_mode,
                latest_per_day=True,
            )
            section = render_theme_history_brief_section(context)
            return section, build_theme_history_brief_compliance_report(section)
        finally:
            safe_close_connection(conn)


def export_sample_brief(
    output: str | Path = DEFAULT_OUTPUT,
    template: str = "portfolio",
    sample_dir: str | Path = DEFAULT_SAMPLE_DIR,
    include_theme_history: bool = True,
    theme_mode: str = "代表口径",
    quiet: bool = False,
) -> dict:
    sample_dir_path = _resolve_path(sample_dir)
    output_path = _resolve_path(output)
    template_mode = PORTFOLIO_BRIEF_MODE if template == "portfolio" else STANDARD_BRIEF_MODE
    brief, metadata, latest_sample_date, sample_summary = _build_sample_observation_brief(sample_dir_path)
    extra_sections: list[str] = []
    theme_history_compliance = {
        "forbidden_hits": [],
        "compliance_label": "未启用",
        "compliance_reason": "未启用主题历史摘要。",
    }
    if include_theme_history:
        theme_history_section, theme_history_compliance = _build_sample_theme_history_section(sample_dir_path, theme_mode)
        extra_sections.append(theme_history_section)
    markdown = render_brief_markdown_with_extra_sections(
        brief,
        template_mode=template_mode,
        metadata=metadata,
        extra_sections=extra_sections,
    )
    compliance = build_brief_compliance_report(markdown)
    structure = validate_brief_markdown_structure(markdown)
    if compliance.get("forbidden_hits") or theme_history_compliance.get("forbidden_hits") or not structure.get("is_valid"):
        return {
            "ok": False,
            "output": str(output_path),
            "latest_sample_date": latest_sample_date,
            "captured_time_count": sample_summary.get("captured_time_count", 0),
            "compliance": compliance,
            "theme_history_compliance": theme_history_compliance,
            "structure": structure,
            "error": "简报合规或结构检查未通过，已取消写入。",
        }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    result = {
        "ok": True,
        "output": str(output_path),
        "latest_sample_date": latest_sample_date,
        "captured_time_count": sample_summary.get("captured_time_count", 0),
        "compliance": compliance,
        "theme_history_compliance": theme_history_compliance,
        "include_theme_history": include_theme_history,
        "structure": structure,
        "error": "",
    }
    if not quiet:
        print("SAMPLE demo brief exported")
        print(f"  output: {output_path}")
        print(f"  latest_sample_date: {latest_sample_date}")
        print(f"  captured_time_count: {sample_summary.get('captured_time_count', 0)}")
        print(f"  compliance_label: {compliance.get('compliance_label')}")
        print(f"  theme_history_compliance_label: {theme_history_compliance.get('compliance_label')}")
        print(f"  forbidden_hits: {compliance.get('forbidden_hits')}")
    return result


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = export_sample_brief(
            output=args.output,
            template=args.template,
            sample_dir=args.sample_dir,
            include_theme_history=args.include_theme_history,
            theme_mode=args.theme_mode,
            quiet=args.quiet,
        )
    except Exception as exc:
        if not args.quiet:
            print(f"SAMPLE demo brief export failed: {exc}")
        return 1
    if not result.get("ok"):
        if not args.quiet:
            print(result.get("error") or "SAMPLE demo brief export failed.")
            print(f"  forbidden_hits: {result.get('compliance', {}).get('forbidden_hits')}")
            print(f"  structure_warnings: {result.get('structure', {}).get('warnings')}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
