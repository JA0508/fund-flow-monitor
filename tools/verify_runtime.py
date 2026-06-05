from __future__ import annotations

import sys
import tomllib
import importlib.util
import re
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import APP_VERSION  # noqa: E402
from src.concept_flow import get_concept_latest_snapshot, summarize_concept_hotspots  # noqa: E402
from src.brief_templates import (  # noqa: E402
    build_brief_compliance_report,
    build_brief_metadata,
    get_brief_template_modes,
    render_brief_markdown_v2,
    validate_brief_markdown_structure,
)
from src.fund_profiles import (  # noqa: E402
    build_fund_summary,
    build_fund_theme_exposure,
    build_holding_related_pool,
    get_funds,
    load_fund_profiles,
    validate_fund_profile,
)
from src.fund_profile_importer import (  # noqa: E402
    SAMPLE_FUND_PROFILE_CSV,
    build_profile_summary_from_csv,
    build_profile_theme_exposure_table,
    load_fund_profiles_csv,
    merge_profile_exposure_with_theme_radar,
    summarize_profile_observations,
    validate_fund_profiles_csv,
    validate_profile_observation_text,
)
from src.intraday_hotspots import (  # noqa: E402
    build_intraday_hotspot_pool,
    build_intraday_hotspot_summary,
    build_theme_intraday_history,
    calculate_intraday_theme_metrics,
)
from src.insight_brief import (  # noqa: E402
    build_data_context_summary,
    build_observation_brief,
    render_brief_markdown,
    summarize_holding_pool_for_brief,
    summarize_intraday_for_brief,
    summarize_multi_day_for_brief,
    summarize_taxonomy_coverage_for_brief,
    summarize_theme_radar_for_brief,
    validate_brief_text,
)
from src.local_warehouse import (  # noqa: E402
    audit_warehouse,
    connect_warehouse,
    get_default_warehouse_path,
    initialize_warehouse,
    query_available_dates,
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
    load_warehouse_if_exists,
    summarize_csv_warehouse_consistency,
    validate_warehouse_explorer_text,
)
from src.multi_day_trends import (  # noqa: E402
    build_daily_theme_snapshots,
    build_multi_day_trend_pool,
    build_multi_day_trend_summary,
    calculate_multi_day_theme_metrics,
)
from src.sample_data import (  # noqa: E402
    build_sample_snapshot_catalog,
    get_latest_sample_date,
    load_sample_snapshot_by_date,
)
from src.snapshot_catalog import (  # noqa: E402
    build_snapshot_catalog,
    get_latest_snapshot_date,
    get_snapshot_summary,
    load_snapshot_by_date,
)
from src.snapshot_quality import (  # noqa: E402
    build_snapshot_quality_report,
    summarize_snapshot_quality,
    validate_snapshot_quality_text,
)
from src.presentation import (  # noqa: E402
    build_demo_walkthrough_steps,
    build_portfolio_intro_context,
    build_screenshot_checklist,
    build_status_badge_config,
    get_display_mode_options,
    validate_presentation_text,
)
from src.storage import find_latest_tick_file, load_latest_ticks  # noqa: E402
from src.theme_concepts import build_theme_concept_summary  # noqa: E402
from src.theme_coverage import (  # noqa: E402
    build_overlap_warning_report,
    build_theme_coverage_report,
)
from src.theme_pool import build_theme_snapshot  # noqa: E402
from src.theme_radar import build_market_temperature, build_theme_radar_snapshot, compare_strict_and_breadth  # noqa: E402
from src.theme_taxonomy import (  # noqa: E402
    audit_theme_name_consistency,
    build_concept_keyword_table,
    build_sector_to_theme_map,
    build_theme_definition_table,
    get_theme_names,
    load_theme_taxonomy,
    validate_theme_taxonomy,
)
from src.theme_history import (  # noqa: E402
    build_theme_history_from_sector_history,
    build_theme_history_quality_report,
    build_theme_status_timeline,
    load_sector_history_from_warehouse,
    validate_theme_history_text,
)
from src.watchlist import filter_watchlist_theme_df, get_watchlist_themes, load_watchlist  # noqa: E402

DEMO_CHECK_FIELDS = ("source", "sector_type", "mode", "data_mode")


def _verify_deployment_files() -> None:
    print("部署配置检查:")
    requirements = PROJECT_ROOT / "requirements.txt"
    config_path = PROJECT_ROOT / ".streamlit/config.toml"
    secrets_example = PROJECT_ROOT / ".streamlit/secrets.example.toml"
    secrets_real = PROJECT_ROOT / ".streamlit/secrets.toml"
    required_packages = {"streamlit", "pandas", "plotly", "akshare", "numpy", "pytest"}
    packages = set()
    if requirements.exists():
        packages = {
            line.strip().split("==")[0].split(">=")[0].split("<=")[0]
            for line in requirements.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
    missing_packages = sorted(required_packages - packages)
    config = {}
    if config_path.exists():
        with config_path.open("rb") as handle:
            config = tomllib.load(handle)
    print(f"  requirements.txt 存在: {requirements.exists()}")
    print(f"  requirements 缺失关键依赖: {missing_packages}")
    print(f"  .streamlit/config.toml 存在: {config_path.exists()}")
    print(f"  theme.base: {config.get('theme', {}).get('base')}")
    print(f"  server.headless: {config.get('server', {}).get('headless')}")
    print(f"  browser.gatherUsageStats: {config.get('browser', {}).get('gatherUsageStats')}")
    print(f"  secrets.example 存在: {secrets_example.exists()}")
    print(f"  secrets.toml 是否被放入项目目录: {secrets_real.exists()}")


def _akshare_info() -> tuple[str, bool]:
    try:
        import akshare as ak
    except ImportError:
        return "not installed", False
    return str(getattr(ak, "__version__", "unknown")), hasattr(ak, "stock_sector_fund_flow_rank")


def _latest_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "captured_at" not in df.columns:
        return pd.DataFrame()
    work = df.copy()
    work["captured_at"] = pd.to_datetime(work["captured_at"], errors="coerce")
    work = work.dropna(subset=["captured_at"])
    if work.empty:
        return pd.DataFrame()
    return work[work["captured_at"].eq(work["captured_at"].max())]


def _sector_stats(df: pd.DataFrame, sector_type: str) -> tuple[int, int]:
    if df.empty or "sector_type" not in df.columns:
        return 0, 0
    sector_df = df[df["sector_type"].eq(sector_type)]
    times = sector_df["captured_time"].nunique() if "captured_time" in sector_df.columns else 0
    return int(len(sector_df)), int(times)


def detect_demo_contamination(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return False
    for field in DEMO_CHECK_FIELDS:
        if field in df.columns:
            values = df[field].fillna("").astype(str).str.upper()
            if values.str.contains("DEMO", regex=False).any():
                return True
    return False


def _has_real_simulated_name(df: pd.DataFrame) -> bool:
    if df is None or df.empty or "sector_name" not in df.columns:
        return False
    return df["sector_name"].fillna("").astype(str).str.contains("模拟", regex=False).any()


def _print_rank(title: str, df: pd.DataFrame) -> None:
    print(title)
    if df.empty:
        print("  <empty>")
        return
    for _, row in df.iterrows():
        print(f"  {row['sector_name']}: {row['main_net_inflow_billion']:.1f} 亿")


def _print_theme_mode(title: str, themes: pd.DataFrame) -> None:
    print(f"{title} 主题快照:")
    if themes.empty:
        print("  <empty>")
        return
    for _, row in themes.iterrows():
        print(
            f"  {row['theme_name']}: {row['main_net_inflow_billion']:.1f} 亿 | "
            f"status={row.get('theme_status', '')} | "
            f"strategy={row.get('match_strategy', '')} | "
            f"used={row.get('used_sectors', '')} | "
            f"source_count={row.get('source_sector_count', 0)}"
        )


def _sectors_set(value: object) -> set[str]:
    if value is None or pd.isna(value):
        return set()
    return {item.strip() for item in str(value).replace(",", "，").split("，") if item.strip()}


def _has_any(sectors: set[str], names: tuple[str, ...]) -> bool:
    return any(name in sectors for name in names)


def _duplicate_layer_warnings(themes: pd.DataFrame) -> list[str]:
    warnings = []
    for _, row in themes.iterrows():
        theme_name = row.get("theme_name", "")
        sectors = _sectors_set(row.get("source_sectors"))
        if {"计算机", "软件开发"}.issubset(sectors) and _has_any(sectors, ("IT服务Ⅱ", "IT服务Ⅲ")):
            warnings.append(f"{theme_name}: source_sectors 同时包含 计算机 + 软件开发 + IT服务Ⅱ/Ⅲ")
        if {"电子", "半导体", "半导体设备"}.issubset(sectors):
            warnings.append(f"{theme_name}: source_sectors 同时包含 电子 + 半导体 + 半导体设备")
        if {"电力设备", "电池"}.issubset(sectors) and _has_any(sectors, ("锂电池", "电池化学品")):
            warnings.append(f"{theme_name}: source_sectors 同时包含 电力设备 + 电池 + 锂电池/电池化学品")
    return warnings


def _semiconductor_comparison(
    strict: pd.DataFrame,
    representative: pd.DataFrame,
    breadth: pd.DataFrame,
) -> None:
    print("半导体/芯片链三种模式对比:")
    strict_row = strict[strict["theme_name"].eq("半导体/芯片链")]
    representative_row = representative[representative["theme_name"].eq("半导体/芯片链")]
    breadth_row = breadth[breadth["theme_name"].eq("半导体/芯片链")]
    if strict_row.empty:
        print("  strict value: <empty>")
    else:
        row = strict_row.iloc[0]
        print(f"  strict value: {row['main_net_inflow_billion']:.1f} 亿 | used={row.get('used_sectors', '')}")
    if representative_row.empty:
        print("  representative value: <empty>")
    else:
        row = representative_row.iloc[0]
        print(f"  representative value: {row['main_net_inflow_billion']:.1f} 亿 | used={row.get('used_sectors', '')}")
    if breadth_row.empty:
        print("  breadth value: <empty>")
    else:
        row = breadth_row.iloc[0]
        print(f"  breadth value: {row['main_net_inflow_billion']:.1f} 亿 | used_count={row.get('used_sector_count', 0)}")


def _best_replay_row(catalog: pd.DataFrame) -> pd.Series | None:
    if catalog is None or catalog.empty:
        return None
    readable = catalog[catalog["is_readable"].fillna(False)]
    if readable.empty:
        return None
    candidates = readable[readable["captured_time_count"].ge(2) & readable["industry_rows"].gt(0)]
    if candidates.empty:
        candidates = readable[readable["industry_rows"].gt(0)]
    if candidates.empty:
        candidates = readable
    return candidates.sort_values(["captured_time_count", "snapshot_date"], ascending=[False, False]).iloc[0]


def _verify_historical_replay(catalog: pd.DataFrame, watchlist_themes: list[str]) -> None:
    print("CSV 快照目录检查:")
    if catalog is None or catalog.empty:
        print("  EMPTY: 暂无本地 CSV 快照。")
        return
    print(f"  可用日期数量: {len(catalog)}")
    print(f"  latest_snapshot_date: {get_latest_snapshot_date(catalog) or '<none>'}")
    print("  available snapshot dates:")
    for _, row in catalog.iterrows():
        print(
            f"    {row['snapshot_date']}: rows={row['row_count']} | "
            f"captured_time={row['captured_time_count']} | quality={row['quality_label']}"
        )

    best = _best_replay_row(catalog)
    if best is None:
        print("  best replay date: <none>")
        return
    best_date = str(best["snapshot_date"])
    best_ticks = load_snapshot_by_date(best_date, str(PROJECT_ROOT / "data/ticks"))
    best_latest = _latest_snapshot(best_ticks[best_ticks["sector_type"].eq("行业资金流")]) if "sector_type" in best_ticks else pd.DataFrame()
    print(f"  best replay date: {best_date}")
    print(f"  best replay captured_time_count: {int(best['captured_time_count'])}")
    print(f"  best replay quality_label: {best['quality_label']}")
    if best_ticks.empty or best_latest.empty:
        print("  historical replay build: <empty>")
        return

    replay_theme = build_theme_snapshot(best_latest, theme_mode="strict_representative")
    replay_radar = build_theme_radar_snapshot(replay_theme)
    fund_profile = load_fund_profiles()
    fund_exposure = build_fund_theme_exposure(get_funds(fund_profile))
    holding_pool = build_holding_related_pool(fund_exposure, replay_radar)
    latest_rank = best_latest.sort_values("main_net_inflow_billion", ascending=False).head(5)
    print(f"  是否可以通过 selected historical date 构建 theme radar: {not replay_radar.empty}")
    print(f"  是否可以通过 selected historical date 构建 holding related pool: {not holding_pool.empty}")
    print(f"  是否可以通过 selected historical date 构建 ranking: {not latest_rank.empty}")

    if int(best["captured_time_count"]) >= 2:
        replay_history = build_theme_intraday_history(best_ticks, mode="breadth")
        replay_metrics = calculate_intraday_theme_metrics(replay_history)
        replay_hotspots = build_intraday_hotspot_pool(replay_metrics, top_n=12)
        print(f"  是否可以用 best replay date 构建 theme_intraday_history: {not replay_history.empty}")
        print(f"  是否可以用 best replay date 构建 intraday hotspot pool: {not replay_hotspots.empty}")
    else:
        print("  best replay captured_time 少于 2，跳过日内热点回放构建。")


def _verify_multi_day_trends(catalog: pd.DataFrame) -> None:
    print("多日主题趋势检查:")
    if catalog is None or catalog.empty:
        print("  本地 CSV 日期不足，暂无法判断多日趋势。")
        return
    available = catalog[catalog["is_readable"].fillna(False) & catalog["industry_rows"].gt(0)]
    print(f"  可用行业缓存日期数量: {len(available)}")
    daily = build_daily_theme_snapshots(catalog, data_dir=str(PROJECT_ROOT / "data/ticks"), mode="strict_representative")
    daily_warnings = daily.attrs.get("warnings", []) if hasattr(daily, "attrs") else []
    date_count = daily["snapshot_date"].nunique() if not daily.empty and "snapshot_date" in daily.columns else 0
    print(f"  是否可以构建 daily_theme_snapshots: {not daily.empty}")
    print(f"  multi_day date_count: {date_count}")
    if daily_warnings:
        print(f"  multi_day warning 数量: {len(daily_warnings)}")
        for warning in daily_warnings[:3]:
            print(f"    warning: {warning}")
    if date_count < 2:
        print("  多日趋势: 可用日期少于 2，暂不判断跨日期变化。")
        return
    metrics = calculate_multi_day_theme_metrics(daily)
    trend_pool = build_multi_day_trend_pool(metrics, top_n=12)
    summary = build_multi_day_trend_summary(trend_pool)
    print(f"  是否可以构建 multi_day_theme_metrics: {not metrics.empty}")
    print(f"  是否可以构建 multi_day_trend_pool: {not trend_pool.empty}")
    print(f"  是否可以构建 multi_day_trend_summary: {bool(summary)}")
    print(f"  summary_label: {summary.get('summary_label')}")
    print(f"  strength_count: {summary.get('strength_count')}")
    print(f"  improving_count: {summary.get('improving_count')}")
    print(f"  pressure_count: {summary.get('pressure_count')}")
    print("  Top 3 trend themes:")
    if trend_pool.empty:
        print("    <empty>")
    else:
        for _, row in trend_pool.head(3).iterrows():
            print(
                f"    {row['theme_name']}: {row['trend_label']} | "
                f"latest={row['latest_value']:.1f} 亿 | change={row['value_change']:.1f} 亿"
            )


def _verify_sample_mode() -> None:
    print("SAMPLE 演示样例数据检查:")
    sample_dir = PROJECT_ROOT / "sample_data/ticks"
    sample_catalog = build_sample_snapshot_catalog(str(sample_dir))
    print(f"  sample_data/ticks 存在: {sample_dir.exists()}")
    print(f"  sample date count: {len(sample_catalog)}")
    if sample_catalog.empty:
        print("  暂无 SAMPLE 样例数据，可运行 python tools/generate_sample_data.py 生成。")
        return

    latest_sample_date = get_latest_sample_date(sample_catalog)
    sample_ticks = load_sample_snapshot_by_date(latest_sample_date or "", str(sample_dir))
    sample_summary = get_snapshot_summary(sample_ticks)
    sample_row = sample_catalog[sample_catalog["snapshot_date"].astype(str).eq(str(latest_sample_date))]
    sample_quality = sample_row["quality_label"].iloc[0] if not sample_row.empty else "<none>"
    has_sample_marker = False
    for column in ("source", "data_mode"):
        if column in sample_ticks.columns:
            has_sample_marker = has_sample_marker or sample_ticks[column].astype(str).str.upper().str.contains("SAMPLE", regex=False).any()
    print(f"  latest sample date: {latest_sample_date or '<none>'}")
    print(f"  sample captured_time_count: {sample_summary.get('captured_time_count')}")
    print(f"  sample quality_label: {sample_quality}")
    print(f"  SAMPLE 数据包含 source/data_mode 标记: {has_sample_marker}")
    print("  sample_data 不会写入 data/ticks；当前检查只读取 sample_data/ticks。")

    sample_latest = _latest_snapshot(sample_ticks[sample_ticks["sector_type"].eq("行业资金流")]) if "sector_type" in sample_ticks else pd.DataFrame()
    sample_theme = build_theme_snapshot(sample_latest, theme_mode="strict_representative")
    sample_radar = build_theme_radar_snapshot(sample_theme)
    sample_history = build_theme_intraday_history(sample_ticks, mode="breadth")
    sample_metrics = calculate_intraday_theme_metrics(sample_history)
    sample_hotspots = build_intraday_hotspot_pool(sample_metrics, top_n=12)
    sample_daily = build_daily_theme_snapshots(sample_catalog, data_dir=str(sample_dir), mode="strict_representative")
    sample_multi_metrics = calculate_multi_day_theme_metrics(sample_daily)
    sample_multi_pool = build_multi_day_trend_pool(sample_multi_metrics, top_n=12)
    sample_fund_profile = load_fund_profiles()
    sample_exposure = build_fund_theme_exposure(get_funds(sample_fund_profile))
    sample_holding = build_holding_related_pool(sample_exposure, sample_radar)
    sample_fund_summary = build_fund_summary(sample_holding)
    sample_data_context = build_data_context_summary(
        latest_sample_date or "<none>",
        "SAMPLE",
        sample_summary,
        "严格代表口径",
    )
    sample_brief = build_observation_brief(
        sample_data_context,
        summarize_theme_radar_for_brief(sample_radar),
        summarize_intraday_for_brief(build_intraday_hotspot_summary(sample_hotspots), sample_hotspots),
        summarize_multi_day_for_brief(build_multi_day_trend_summary(sample_multi_pool), sample_multi_pool),
        summarize_holding_pool_for_brief(sample_fund_summary),
        summarize_taxonomy_coverage_for_brief(build_theme_coverage_report(sample_latest, load_theme_taxonomy()), {}),
    )
    sample_markdown = render_brief_markdown(sample_brief)
    sample_forbidden_hits = validate_brief_text(sample_markdown)
    print(f"  是否可以用 sample 构建 theme radar: {not sample_radar.empty}")
    print(f"  是否可以用 sample 构建 intraday hotspot pool: {not sample_hotspots.empty}")
    print(f"  是否可以用 sample 构建 multi-day trend pool: {not sample_multi_pool.empty}")
    print(f"  是否可以用 sample 构建 holding related pool: {not sample_holding.empty}")
    print(f"  是否可以用 sample 构建 observation brief: {bool(sample_brief)}")
    print(f"  sample brief forbidden_hits: {sample_forbidden_hits}")


def _verify_theme_taxonomy(latest_df: pd.DataFrame, watchlist_themes: list[str], fund_exposure: pd.DataFrame) -> None:
    print("主题库治理检查:")
    taxonomy = load_theme_taxonomy()
    warnings = validate_theme_taxonomy(taxonomy)
    fund_themes = fund_exposure["theme_name"].dropna().astype(str).unique().tolist() if fund_exposure is not None and not fund_exposure.empty else []
    consistency = audit_theme_name_consistency(taxonomy, watchlist_themes, fund_themes)
    definition = build_theme_definition_table(taxonomy)
    sector_map = build_sector_to_theme_map(taxonomy)
    keywords = build_concept_keyword_table(taxonomy)
    coverage = build_theme_coverage_report(latest_df, taxonomy)
    overlap = build_overlap_warning_report(taxonomy)
    print(f"  taxonomy_name: {taxonomy.get('taxonomy_name')}")
    print(f"  theme_count: {len(get_theme_names(taxonomy))}")
    print(f"  taxonomy warning 数量: {len(warnings)}")
    print(f"  watchlist 全部存在于 taxonomy: {not consistency.get('watchlist_missing_in_taxonomy')}")
    print(f"  fund_profiles 主题全部存在于 taxonomy: {not consistency.get('fund_profile_missing_in_taxonomy')}")
    print(f"  是否可以构建 theme_definition_table: {not definition.empty}")
    print(f"  是否可以构建 sector_to_theme_map: {not sector_map.empty}")
    print(f"  是否可以构建 concept_keyword_table: {not keywords.empty}")
    print(f"  是否可以构建 theme_coverage_report: {bool(coverage)}")
    print(f"  是否可以构建 overlap_warning_report: {overlap is not None}")
    print(f"  coverage_ratio: {coverage.get('coverage_ratio', 0):.2%}")
    print(f"  coverage_label: {coverage.get('coverage_label')}")
    high_flow = coverage.get("high_flow_uncovered_df", pd.DataFrame())
    print(f"  high_flow_uncovered_count: {len(high_flow) if isinstance(high_flow, pd.DataFrame) else 0}")
    print(f"  overlap warning count: {len(overlap) if isinstance(overlap, pd.DataFrame) else 0}")


def _verify_fund_profile_csv(radar: pd.DataFrame, taxonomy: dict) -> None:
    print("基金/ETF 主题暴露 CSV 检查:")
    csv_path = PROJECT_ROOT / SAMPLE_FUND_PROFILE_CSV
    csv_df = load_fund_profiles_csv(str(csv_path))
    validation = validate_fund_profiles_csv(csv_df, taxonomy)
    summary = build_profile_summary_from_csv(csv_df, validation)
    exposure = build_profile_theme_exposure_table(csv_df, taxonomy)
    merged = merge_profile_exposure_with_theme_radar(exposure, radar)
    observation = summarize_profile_observations(merged)
    text_parts = []
    if not merged.empty and "observation_reason" in merged.columns:
        text_parts.extend(merged["observation_reason"].dropna().astype(str).tolist())
    if not observation.empty and "profile_observation_reason" in observation.columns:
        text_parts.extend(observation["profile_observation_reason"].dropna().astype(str).tolist())
    forbidden_hits = validate_profile_observation_text(" ".join(text_parts))
    print(f"  fund profile csv path: {SAMPLE_FUND_PROFILE_CSV}")
    print(f"  csv exists: {csv_path.exists()}")
    print(f"  csv profile count: {validation.get('profile_count')}")
    print(f"  csv row count: {validation.get('row_count')}")
    print(f"  csv validation label: {validation.get('validation_label')}")
    print(f"  csv warning count: {validation.get('warning_count')}")
    print(f"  csv error count: {validation.get('error_count')}")
    print(f"  是否可以构建 profile summary: {not summary.empty}")
    print(f"  是否可以构建 profile theme exposure table: {not exposure.empty}")
    print(f"  是否可以合并当前 theme_radar: {not merged.empty}")
    print(f"  是否可以生成 profile observation summary: {not observation.empty}")
    print(f"  profile observation forbidden_hits: {forbidden_hits}")
    if validation.get("unknown_themes"):
        print(f"  unknown themes: {validation.get('unknown_themes')}")


def _verify_snapshot_quality() -> None:
    print("CSV 快照质量治理检查:")
    report = build_snapshot_quality_report(
        directory=str(PROJECT_ROOT / "data/ticks"),
        sample_directory=str(PROJECT_ROOT / "sample_data/ticks"),
    )
    summary = summarize_snapshot_quality(report)
    forbidden_hits = validate_snapshot_quality_text(summary)
    sample_catalog = report.get("sample_catalog_df", pd.DataFrame())
    collect_script = PROJECT_ROOT / "tools/collect_market_snapshot.py"
    spec = importlib.util.spec_from_file_location("collect_market_snapshot", collect_script)
    collect_import_ok = spec is not None and spec.loader is not None
    if collect_import_ok and spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        collect_import_ok = hasattr(module, "build_parser") and hasattr(module, "collect_once")
    print(f"  snapshot_quality_report_label: {report.get('report_label')}")
    print(f"  local_file_count: {report.get('local_file_count')}")
    print(f"  sample_file_count: {report.get('sample_file_count')}")
    print(f"  local warning/error: {report.get('local_warning_count')} / {report.get('local_error_count')}")
    print(f"  sample warning/error: {report.get('sample_warning_count')} / {report.get('sample_error_count')}")
    print(f"  sample_catalog row count: {len(sample_catalog) if isinstance(sample_catalog, pd.DataFrame) else 0}")
    print(f"  snapshot_quality_forbidden_hits: {forbidden_hits}")
    print(f"  collect_market_snapshot.py import: {collect_import_ok}")
    print("  verify_runtime 不执行真实采集；如需手动检查可运行 python tools/collect_market_snapshot.py --no-network。")


def _verify_local_warehouse() -> None:
    print("SQLite warehouse readiness 检查:")
    with tempfile.TemporaryDirectory() as tmp_dir:
        warehouse_path = Path(tmp_dir) / "fund_flow.sqlite"
        conn = connect_warehouse(str(warehouse_path))
        try:
            initialize_warehouse(conn)
            rebuild = rebuild_warehouse_from_csv_directory(
                conn,
                str(PROJECT_ROOT / "sample_data/ticks"),
                "SAMPLE",
                clear_source=True,
            )
            summary = query_warehouse_summary(conn)
            dates = query_available_dates(conn)
            audit = audit_warehouse(conn)
            forbidden_hits = validate_warehouse_text(summarize_warehouse_status(summary, audit))
            explorer_summary = build_warehouse_explorer_summary(conn)
            source_summary_df = get_warehouse_source_type_summary(conn)
            date_overview_df = get_warehouse_date_overview(conn)
            consistency = build_csv_warehouse_consistency_report(
                conn,
                local_csv_dir=str(PROJECT_ROOT / "data/ticks"),
                sample_csv_dir=str(PROJECT_ROOT / "sample_data/ticks"),
            )
            explorer_forbidden_hits = validate_warehouse_explorer_text(summarize_csv_warehouse_consistency(consistency))
            sector_history = load_sector_history_from_warehouse(conn, source_type="SAMPLE", latest_per_day=True)
            theme_history = build_theme_history_from_sector_history(sector_history, load_theme_taxonomy(), theme_mode="代表口径")
            theme_timeline = build_theme_status_timeline(theme_history)
            theme_quality = build_theme_history_quality_report(sector_history, theme_history)
            theme_history_forbidden_hits = validate_theme_history_text(str(theme_quality.get("quality_label", "")))
        finally:
            conn.close()
    default_warehouse_exists = (PROJECT_ROOT / get_default_warehouse_path()).exists()
    default_conn, default_status = load_warehouse_if_exists(str(PROJECT_ROOT / get_default_warehouse_path()))
    default_source_count = 0
    try:
        if default_conn is not None:
            default_source_df = get_warehouse_source_type_summary(default_conn)
            default_source_count = int(default_source_df["source_type"].nunique()) if not default_source_df.empty else 0
    finally:
        if default_conn is not None:
            default_conn.close()
    print(f"  temp_warehouse_rebuild_label: {rebuild.get('rebuild_label')}")
    print(f"  temp_warehouse_row_count: {summary.get('snapshot_row_count')}")
    print(f"  temp_warehouse_file_count: {summary.get('snapshot_file_count')}")
    print(f"  temp_warehouse_available_date_count: {len(dates)}")
    print(f"  temp_warehouse_audit_label: {audit.get('audit_label')}")
    print(f"  temp_explorer_label: {explorer_summary.get('explorer_label')}")
    print(f"  temp_source_type_count: {source_summary_df['source_type'].nunique() if not source_summary_df.empty else 0}")
    print(f"  temp_date_count: {date_overview_df['data_date'].nunique() if not date_overview_df.empty else 0}")
    print(f"  temp_row_count: {explorer_summary.get('row_count')}")
    print(f"  csv_warehouse_consistency_label: {consistency.get('overall_label')}")
    print(f"  temp_sector_history_row_count: {len(sector_history)}")
    print(f"  temp_theme_history_row_count: {len(theme_history)}")
    print(f"  temp_theme_history_date_count: {theme_history['data_date'].nunique() if not theme_history.empty else 0}")
    print(f"  temp_theme_status_timeline_rows: {len(theme_timeline)}")
    print(f"  temp_theme_history_quality_label: {theme_quality.get('quality_label')}")
    print(f"  warehouse_forbidden_hits: {forbidden_hits}")
    print(f"  warehouse_explorer_forbidden_hits: {explorer_forbidden_hits}")
    print(f"  theme_history_forbidden_hits: {theme_history_forbidden_hits}")
    print(f"  default_warehouse_exists: {default_warehouse_exists}")
    print(f"  default_warehouse_status: {default_status.get('status_label')}")
    print(f"  default_warehouse_source_type_count: {default_source_count}")
    print("  verify_runtime 只写入临时 SQLite，不写默认 data/warehouse。")


def _find_broken_readme_images() -> list[str]:
    readme = PROJECT_ROOT / "README.md"
    if not readme.exists():
        return ["README.md missing"]
    text = readme.read_text(encoding="utf-8")
    links = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    broken = []
    for link in links:
        if link.startswith(("http://", "https://", "data:")):
            continue
        path = (PROJECT_ROOT / link).resolve()
        if not path.exists():
            broken.append(link)
    return broken


def _verify_presentation_readiness(selected_date: str, data_status: str) -> None:
    print("作品集展示 readiness 检查:")
    statuses = ["LIVE", "CACHE", "HISTORY", "SAMPLE", "DEMO", "EMPTY"]
    badges = [build_status_badge_config(status) for status in statuses]
    intro = build_portfolio_intro_context(APP_VERSION, data_status, selected_date, "作品集演示模式")
    checklist = build_screenshot_checklist()
    steps = build_demo_walkthrough_steps()
    text_parts = [
        intro.get("title", ""),
        intro.get("subtitle", ""),
        intro.get("value_proposition", ""),
        " ".join(intro.get("key_capabilities", [])),
        " ".join(intro.get("boundary_notes", [])),
    ]
    for row in checklist:
        text_parts.extend(str(row.get(key, "")) for key in ("screenshot_name", "what_to_capture", "notes"))
    for row in steps:
        text_parts.extend(str(row.get(key, "")) for key in ("step_title", "description", "expected_user_takeaway"))
    forbidden_hits = validate_presentation_text(" ".join(text_parts))
    broken_images = _find_broken_readme_images()
    print(f"  portfolio_mode_available: {'作品集演示模式' in get_display_mode_options()}")
    print(f"  screenshot_checklist_count: {len(checklist)}")
    print(f"  demo_walkthrough_step_count: {len(steps)}")
    print(f"  presentation_forbidden_hits: {forbidden_hits}")
    print(f"  status_badge_supported_count: {sum(1 for badge in badges if badge.get('status') in statuses)}")
    print(f"  README broken image count: {len(broken_images)}")
    if broken_images:
        print(f"  README broken images: {broken_images}")


def _readme_links_exist(paths: tuple[str, ...]) -> bool:
    readme = PROJECT_ROOT / "README.md"
    if not readme.exists():
        return False
    text = readme.read_text(encoding="utf-8")
    for rel_path in paths:
        if rel_path not in text or not (PROJECT_ROOT / rel_path).exists():
            return False
    return True


def _verify_brief_template_readiness(observation_brief: dict, selected_date: str) -> None:
    print("观察简报模板 / demo brief readiness 检查:")
    metadata = build_brief_metadata(
        selected_date,
        "SAMPLE",
        "严格代表口径",
        "v1.9",
        "sample_data/ticks",
    )
    markdown = render_brief_markdown_v2(observation_brief, template_mode="作品集演示简报", metadata=metadata)
    compliance = build_brief_compliance_report(markdown)
    structure = validate_brief_markdown_structure(markdown)
    export_script = PROJECT_ROOT / "tools/export_sample_brief.py"
    spec = importlib.util.spec_from_file_location("export_sample_brief", export_script)
    export_import_ok = spec is not None and spec.loader is not None
    if export_import_ok and spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        export_import_ok = hasattr(module, "export_sample_brief") and hasattr(module, "build_parser")

    demo_brief_path = PROJECT_ROOT / "docs/demo_briefs/sample_observation_brief.md"
    demo_compliance = {"compliance_label": "<missing>", "forbidden_hits": []}
    if demo_brief_path.exists():
        demo_text = demo_brief_path.read_text(encoding="utf-8")
        demo_compliance = build_brief_compliance_report(demo_text)
    readme_links_valid = _readme_links_exist(
        (
            "docs/demo_briefs/sample_observation_brief.md",
            "docs/RELEASE_CHECKLIST.md",
        )
    )
    print(f"  brief_template_modes: {get_brief_template_modes()}")
    print(f"  render_brief_markdown_v2 compliance_label: {compliance.get('compliance_label')}")
    print(f"  render_brief_markdown_v2 structure_valid: {structure.get('is_valid')}")
    print(f"  export_sample_brief.py import: {export_import_ok}")
    print(f"  demo brief exists: {demo_brief_path.exists()}")
    print(f"  demo_brief_compliance_label: {demo_compliance.get('compliance_label')}")
    print(f"  demo_brief_forbidden_hits: {demo_compliance.get('forbidden_hits')}")
    print(f"  release_checklist_exists: {(PROJECT_ROOT / 'docs/RELEASE_CHECKLIST.md').exists()}")
    print(f"  readme_demo_links_valid: {readme_links_valid}")


def main() -> int:
    ak_version, has_api = _akshare_info()
    latest_file = find_latest_tick_file()
    ticks = load_latest_ticks()
    latest = _latest_snapshot(ticks)
    snapshot_catalog = build_snapshot_catalog(str(PROJECT_ROOT / "data/ticks"))

    print(f"项目路径: {PROJECT_ROOT}")
    print(f"Python 版本: {sys.version.split()[0]}")
    print(f"AKShare 版本: {ak_version}")
    print(f"存在 stock_sector_fund_flow_rank: {has_api}")
    print(f"当前 CSV 文件路径: {latest_file or '<none>'}")
    print(f"CSV 行数: {len(ticks)}")
    print(f"unique captured_time 数量: {ticks['captured_time'].nunique() if 'captured_time' in ticks else 0}")
    industry_rows, industry_times = _sector_stats(ticks, "行业资金流")
    concept_rows, concept_times = _sector_stats(ticks, "概念资金流")
    print(f"行业资金流 rows / unique captured_time: {industry_rows} / {industry_times}")
    print(f"概念资金流 rows / unique captured_time: {concept_rows} / {concept_times}")
    latest_time = latest["captured_time"].iloc[0] if not latest.empty and "captured_time" in latest else "<none>"
    print(f"最新 captured_time: {latest_time}")
    sector_type = latest["sector_type"].iloc[0] if not latest.empty and "sector_type" in latest else "<none>"
    print(f"当前 sector_type: {sector_type}")
    _verify_deployment_files()
    _verify_historical_replay(snapshot_catalog, [])
    _verify_multi_day_trends(snapshot_catalog)
    _verify_sample_mode()

    if not latest.empty:
        _print_rank("最新 Top 5 净流入:", latest.sort_values("main_net_inflow_billion", ascending=False).head(5))
        _print_rank("最新 Top 5 净流出:", latest.sort_values("main_net_inflow_billion", ascending=True).head(5))
    else:
        _print_rank("最新 Top 5 净流入:", pd.DataFrame())
        _print_rank("最新 Top 5 净流出:", pd.DataFrame())

    has_demo = detect_demo_contamination(ticks)
    print("DEMO 检测仅检查 source / sector_type / mode 字段，不检查真实板块名称。")
    print(f"当前是否存在 DEMO 数据混入真实 CSV: {has_demo}")
    if _has_real_simulated_name(ticks):
        print("检测到真实板块名包含‘模拟’，未按 DEMO 处理。")

    suspicious_units = False
    if not ticks.empty:
        billion = pd.to_numeric(ticks.get("main_net_inflow_billion"), errors="coerce")
        yuan = pd.to_numeric(ticks.get("main_net_inflow_yuan"), errors="coerce")
        mismatch = (yuan / 100_000_000 - billion).abs() > 0.01
        suspicious_units = bool((billion.abs() > 10_000).any() or mismatch.fillna(False).any())
    print(f"当前是否存在单位疑似异常: {suspicious_units}")

    strict = build_theme_snapshot(latest, theme_mode="strict_representative")
    representative = build_theme_snapshot(latest, theme_mode="representative")
    breadth = build_theme_snapshot(latest, theme_mode="breadth")
    print(f"是否可以构建 strict_representative 主题快照: {not strict.empty}")
    print(f"是否可以构建 representative 主题快照: {not representative.empty}")
    print(f"是否可以构建 breadth 主题快照: {not breadth.empty}")
    _print_theme_mode("strict_representative", strict)
    _print_theme_mode("representative", representative)
    _print_theme_mode("breadth", breadth)
    _semiconductor_comparison(strict, representative, breadth)

    radar = build_theme_radar_snapshot(strict)
    temperature = build_market_temperature(radar)
    watchlist = load_watchlist()
    watchlist_themes = get_watchlist_themes(watchlist)
    watchlist_df = filter_watchlist_theme_df(radar, watchlist_themes)
    divergence = compare_strict_and_breadth(strict, breadth)
    watchlist_divergence = filter_watchlist_theme_df(divergence, watchlist_themes)
    print(f"是否可以构建 theme_radar_snapshot: {not radar.empty}")
    print(f"是否可以构建 market_temperature: {bool(temperature)}")
    print(f"是否可以加载 watchlist.json: {bool(watchlist_themes)}")
    print(f"watchlist themes: {watchlist_themes}")
    print(f"watchlist 当前匹配主题数: {len(watchlist_df)}")
    print(f"market_temperature_label: {temperature.get('market_temperature_label')}")
    print(f"positive_count: {temperature.get('positive_count')}")
    print(f"negative_count: {temperature.get('negative_count')}")

    fund_profile = load_fund_profiles()
    fund_profile_warnings = validate_fund_profile(fund_profile)
    fund_exposure = build_fund_theme_exposure(get_funds(fund_profile))
    holding_pool = build_holding_related_pool(fund_exposure, radar)
    fund_summary = build_fund_summary(holding_pool)
    missing_themes = []
    if not fund_exposure.empty and not radar.empty:
        radar_themes = set(radar["theme_name"].dropna().astype(str))
        missing_themes = sorted(set(fund_exposure["theme_name"].dropna().astype(str)) - radar_themes)
    print(f"是否可以加载 fund_profiles.json: {bool(get_funds(fund_profile))}")
    print(f"fund profile_name: {fund_profile.get('profile_name')}")
    print(f"fund count: {len(get_funds(fund_profile))}")
    print(f"fund profile warning 数量: {len(fund_profile_warnings)}")
    print(f"是否可以构建 fund theme exposure: {not fund_exposure.empty}")
    print(f"是否可以构建 holding related pool: {not holding_pool.empty}")
    print(f"是否可以构建 fund summary: {not fund_summary.empty}")
    print(f"exposure rows: {len(fund_exposure)}")
    print(f"holding related rows: {len(holding_pool)}")
    if missing_themes:
        print(f"fund profile theme warning: 以下主题未在当前 theme_radar_df 中匹配: {missing_themes}")
    taxonomy = load_theme_taxonomy()
    _verify_theme_taxonomy(latest, watchlist_themes, fund_exposure)
    _verify_fund_profile_csv(radar, taxonomy)
    _verify_snapshot_quality()
    _verify_local_warehouse()
    print("fund summary Top 3:")
    if fund_summary.empty:
        print("  <empty>")
    else:
        for _, row in fund_summary.head(3).iterrows():
            print(
                f"  {row['fund_name']} ({row['fund_code']}): "
                f"score={row['weighted_impact_score']:.2f} | {row['fund_impact_label']}"
            )

    intraday_history = build_theme_intraday_history(ticks, mode="breadth")
    intraday_warnings = intraday_history.attrs.get("warnings", []) if hasattr(intraday_history, "attrs") else []
    intraday_snapshot_count = (
        intraday_history["captured_time"].nunique()
        if not intraday_history.empty and "captured_time" in intraday_history.columns
        else 0
    )
    intraday_metrics = pd.DataFrame()
    hotspot_pool = pd.DataFrame()
    hotspot_summary = {}
    print(f"是否可以构建 theme_intraday_history: {not intraday_history.empty}")
    print(f"intraday snapshot_count: {intraday_snapshot_count}")
    if intraday_warnings:
        print(f"intraday warning 数量: {len(intraday_warnings)}")
        for warning in intraday_warnings[:3]:
            print(f"  warning: {warning}")
    if intraday_snapshot_count < 2:
        print("日内热点池: captured_time 少于 2，暂不判断日内变化。")
    else:
        intraday_metrics = calculate_intraday_theme_metrics(intraday_history)
        hotspot_pool = build_intraday_hotspot_pool(intraday_metrics, top_n=12)
        hotspot_summary = build_intraday_hotspot_summary(hotspot_pool)
        print(f"是否可以构建 intraday metrics: {not intraday_metrics.empty}")
        print(f"是否可以构建 hotspot_pool: {not hotspot_pool.empty}")
        print(f"是否可以构建 hotspot_summary: {bool(hotspot_summary)}")
        print(f"hotspot total themes: {hotspot_summary.get('total_themes')}")
        print(f"hotspot summary_label: {hotspot_summary.get('summary_label')}")
        print(f"positive_hotspot_count: {hotspot_summary.get('positive_hotspot_count')}")
        print(f"improving_count: {hotspot_summary.get('improving_count')}")
        print(f"pressure_count: {hotspot_summary.get('pressure_count')}")
        print("Top 3 hotspot themes:")
        if hotspot_pool.empty:
            print("  <empty>")
        else:
            for _, row in hotspot_pool.head(3).iterrows():
                print(
                    f"  {row['theme_name']}: {row['hotspot_label']} | "
                    f"latest={row['latest_value']:.1f} 亿 | change={row['value_change']:.1f} 亿 | "
                    f"rank_change={row['rank_change']}"
                )

    daily_for_brief = build_daily_theme_snapshots(snapshot_catalog, data_dir=str(PROJECT_ROOT / "data/ticks"), mode="strict_representative")
    multi_day_metrics_for_brief = calculate_multi_day_theme_metrics(daily_for_brief)
    multi_day_pool_for_brief = build_multi_day_trend_pool(multi_day_metrics_for_brief, top_n=12)
    multi_day_summary_for_brief = build_multi_day_trend_summary(multi_day_pool_for_brief)
    taxonomy_for_brief = load_theme_taxonomy()
    coverage_for_brief = build_theme_coverage_report(latest, taxonomy_for_brief)
    consistency_for_brief = audit_theme_name_consistency(taxonomy_for_brief, watchlist_themes, fund_exposure["theme_name"].dropna().astype(str).unique().tolist())
    snapshot_summary = get_snapshot_summary(ticks)
    selected_date = (
        str(latest["trade_date"].dropna().iloc[0])
        if not latest.empty and "trade_date" in latest.columns and not latest["trade_date"].dropna().empty
        else "<none>"
    )
    data_context = build_data_context_summary(
        selected_date,
        "CACHE",
        snapshot_summary,
        "严格代表口径",
    )
    radar_summary = summarize_theme_radar_for_brief(radar)
    intraday_brief = summarize_intraday_for_brief(hotspot_summary, hotspot_pool)
    multi_day_brief = summarize_multi_day_for_brief(multi_day_summary_for_brief, multi_day_pool_for_brief)
    holding_brief = summarize_holding_pool_for_brief(fund_summary)
    coverage_brief = summarize_taxonomy_coverage_for_brief(coverage_for_brief, consistency_for_brief)
    observation_brief = build_observation_brief(
        data_context,
        radar_summary,
        intraday_brief,
        multi_day_brief,
        holding_brief,
        coverage_brief,
    )
    brief_markdown = render_brief_markdown(observation_brief)
    forbidden_hits = validate_brief_text(brief_markdown)
    print("观察简报检查:")
    print("  是否可以导入 insight_brief: True")
    print(f"  是否可以构建 data_context_summary: {bool(data_context)}")
    print(f"  是否可以构建 radar_summary: {bool(radar_summary)}")
    print(f"  是否可以构建 intraday summary: {bool(intraday_brief)}")
    print(f"  是否可以构建 multi-day summary: {bool(multi_day_brief)}")
    print(f"  是否可以构建 holding summary: {bool(holding_brief)}")
    print(f"  是否可以构建 coverage summary: {bool(coverage_brief)}")
    print(f"  是否可以构建 observation brief: {bool(observation_brief)}")
    print(f"  是否可以生成 markdown: {bool(brief_markdown)}")
    print(f"  validate_brief_text 是否通过: {not forbidden_hits}")
    print(f"  brief_title: {observation_brief.get('brief_title')}")
    print(f"  executive_summary 前 80 字: {observation_brief.get('executive_summary', '')[:80]}")
    print(f"  key_points 数量: {len(observation_brief.get('key_points', []))}")
    print(f"  forbidden_hits: {forbidden_hits}")
    _verify_brief_template_readiness(observation_brief, selected_date)
    _verify_presentation_readiness(selected_date, "CACHE")

    concept_latest = get_concept_latest_snapshot(ticks)
    if concept_latest.empty:
        print("暂无概念资金流缓存，可通过页面手动刷新生成。")
        print("是否可以构建 concept_hotspots: False")
        print("是否可以构建 theme_concept_summary: False")
    else:
        concept_hotspots = summarize_concept_hotspots(concept_latest)
        theme_concepts = build_theme_concept_summary(concept_latest, watchlist_themes)
        print(f"是否可以构建 concept_hotspots: {not concept_hotspots.empty}")
        print(f"是否可以构建 theme_concept_summary: {not theme_concepts.empty}")
        print("概念热点 Top 5:")
        for _, row in concept_hotspots.head(5).iterrows():
            print(f"  {row['concept_name']}: {row['main_net_inflow_billion']:.1f} 亿 | {row['hotspot_status']}")
        print("主题相关概念摘要:")
        for _, row in theme_concepts.iterrows():
            print(
                f"  {row['theme_name']}: {row['concept_net_inflow_billion']:.1f} 亿 | "
                f"{row['concept_status']} | top={row['top_concepts']}"
            )

    print("top divergence 3 条:")
    if watchlist_divergence.empty:
        print("  <empty>")
    else:
        for _, row in watchlist_divergence.head(3).iterrows():
            print(
                f"  {row['theme_name']}: {row['divergence_type']} | "
                f"strict={row['strict_value']:.1f} 亿 | breadth={row['breadth_value']:.1f} 亿"
            )

    warnings = _duplicate_layer_warnings(breadth)
    if warnings:
        print("潜在重复层级 warning:")
        for warning in warnings:
            print(f"  warning: {warning}")
    else:
        print("潜在重复层级 warning: <none>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
