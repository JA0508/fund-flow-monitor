from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.concept_flow import get_concept_latest_snapshot, summarize_concept_hotspots  # noqa: E402
from src.fund_profiles import (  # noqa: E402
    build_fund_summary,
    build_fund_theme_exposure,
    build_holding_related_pool,
    get_funds,
    load_fund_profiles,
    validate_fund_profile,
)
from src.storage import find_latest_tick_file, load_latest_ticks  # noqa: E402
from src.theme_concepts import build_theme_concept_summary  # noqa: E402
from src.theme_pool import build_theme_snapshot  # noqa: E402
from src.theme_radar import build_market_temperature, build_theme_radar_snapshot, compare_strict_and_breadth  # noqa: E402
from src.watchlist import filter_watchlist_theme_df, get_watchlist_themes, load_watchlist  # noqa: E402

DEMO_CHECK_FIELDS = ("source", "sector_type", "mode", "data_mode")


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


def main() -> int:
    ak_version, has_api = _akshare_info()
    latest_file = find_latest_tick_file()
    ticks = load_latest_ticks()
    latest = _latest_snapshot(ticks)

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
    print("fund summary Top 3:")
    if fund_summary.empty:
        print("  <empty>")
    else:
        for _, row in fund_summary.head(3).iterrows():
            print(
                f"  {row['fund_name']} ({row['fund_code']}): "
                f"score={row['weighted_impact_score']:.2f} | {row['fund_impact_label']}"
            )

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
