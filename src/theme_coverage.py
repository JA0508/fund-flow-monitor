from __future__ import annotations

from collections import defaultdict

import pandas as pd

from src.theme_taxonomy import build_sector_to_theme_map, build_theme_definition_table


def _normalize(value: object) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()


def _coverage_label(ratio: float) -> tuple[str, str]:
    if ratio >= 0.7:
        return "主题覆盖较高", "当前主题库覆盖了较多资金流板块，适合继续观察并做细节校准。"
    if ratio >= 0.4:
        return "主题覆盖中等", "当前主题库覆盖中等，部分高资金流板块尚未纳入主题池，适合后续人工校准。"
    return (
        "主题覆盖偏低",
        "当前主题库只覆盖重点基金观察主题，覆盖率偏低不代表数据异常；较多资金流板块未纳入主题池，适合后续人工扩展。",
    )


def _sector_role_map(taxonomy: dict) -> dict[str, set[str]]:
    sector_map = build_sector_to_theme_map(taxonomy)
    roles: dict[str, set[str]] = defaultdict(set)
    if sector_map.empty:
        return roles
    for _, row in sector_map.iterrows():
        roles[_normalize(row.get("sector_name"))].add(_normalize(row.get("sector_role")))
    return roles


def build_theme_coverage_report(
    latest_df: pd.DataFrame,
    taxonomy: dict,
    top_n_uncovered: int = 20,
) -> dict:
    if latest_df is None or latest_df.empty:
        empty = pd.DataFrame()
        return {
            "total_sectors": 0,
            "covered_sector_count": 0,
            "uncovered_sector_count": 0,
            "coverage_ratio": 0.0,
            "primary_covered_count": 0,
            "related_covered_count": 0,
            "top_uncovered_sectors_df": empty,
            "high_flow_uncovered_df": empty,
            "duplicated_sector_df": build_overlap_warning_report(taxonomy),
            "coverage_label": "暂无可审计快照",
            "coverage_reason": "当前 active_ticks_df 为空，暂无可审计资金流快照。",
        }
    df = latest_df.copy()
    if "sector_name" not in df.columns:
        df["sector_name"] = ""
    df["sector_name"] = df["sector_name"].map(_normalize)
    df["main_net_inflow_billion"] = pd.to_numeric(df.get("main_net_inflow_billion"), errors="coerce").fillna(0.0)
    df = df[df["sector_name"].ne("")]
    roles = _sector_role_map(taxonomy)
    df["_roles"] = df["sector_name"].map(lambda sector: roles.get(sector, set()))
    df["_covered"] = df["_roles"].map(bool)
    df["_primary"] = df["_roles"].map(lambda value: "primary" in value)
    df["_related"] = df["_roles"].map(lambda value: "related" in value)
    total = int(len(df))
    covered = int(df["_covered"].sum())
    uncovered = total - covered
    ratio = covered / total if total else 0.0
    label, reason = _coverage_label(ratio)
    uncovered_df = df[~df["_covered"]].copy()
    uncovered_df["abs_main_net_inflow_billion"] = uncovered_df["main_net_inflow_billion"].abs()
    top_uncovered = (
        uncovered_df.sort_values("abs_main_net_inflow_billion", ascending=False)
        .head(top_n_uncovered)[["sector_name", "main_net_inflow_billion", "abs_main_net_inflow_billion"]]
        .reset_index(drop=True)
    )
    high_flow = (
        uncovered_df[uncovered_df["abs_main_net_inflow_billion"].ge(20)]
        .sort_values("abs_main_net_inflow_billion", ascending=False)[["sector_name", "main_net_inflow_billion", "abs_main_net_inflow_billion"]]
        .reset_index(drop=True)
    )
    return {
        "total_sectors": total,
        "covered_sector_count": covered,
        "uncovered_sector_count": uncovered,
        "coverage_ratio": ratio,
        "primary_covered_count": int(df["_primary"].sum()),
        "related_covered_count": int(df["_related"].sum()),
        "top_uncovered_sectors_df": top_uncovered,
        "high_flow_uncovered_df": high_flow,
        "duplicated_sector_df": build_overlap_warning_report(taxonomy),
        "coverage_label": label,
        "coverage_reason": reason,
    }


def build_theme_usage_report(
    theme_snapshot_df: pd.DataFrame,
    taxonomy: dict,
) -> pd.DataFrame:
    definitions = build_theme_definition_table(taxonomy)
    if definitions.empty:
        return pd.DataFrame()
    base = definitions[["theme_name", "theme_group", "primary_sectors", "related_sectors"]].copy()
    base["taxonomy_primary_count"] = base["primary_sectors"].map(lambda value: len([item for item in str(value).split("，") if item]))
    base["taxonomy_related_count"] = base["related_sectors"].map(lambda value: len([item for item in str(value).split("，") if item]))
    if theme_snapshot_df is None or theme_snapshot_df.empty:
        base["main_net_inflow_billion"] = pd.NA
        base["theme_status"] = "未匹配"
        base["match_strategy"] = "no_snapshot"
        base["source_count"] = 0
        base["has_primary_match"] = False
        base["used_sectors"] = ""
        base["coverage_note"] = "当前快照中未构建该主题。"
        return base[
            [
                "theme_name",
                "theme_group",
                "main_net_inflow_billion",
                "theme_status",
                "match_strategy",
                "source_count",
                "has_primary_match",
                "used_sectors",
                "taxonomy_primary_count",
                "taxonomy_related_count",
                "coverage_note",
            ]
        ]
    snapshot = theme_snapshot_df.copy()
    if "theme_name" not in snapshot.columns and "sector_name" in snapshot.columns:
        snapshot["theme_name"] = snapshot["sector_name"]
    merged = base.merge(
        snapshot[
            [
                column
                for column in [
                    "theme_name",
                    "main_net_inflow_billion",
                    "theme_status",
                    "match_strategy",
                    "source_sector_count",
                    "used_sectors",
                ]
                if column in snapshot.columns
            ]
        ],
        on="theme_name",
        how="left",
    )
    if "source_sector_count" not in merged.columns:
        merged["source_sector_count"] = 0
    merged["source_count"] = pd.to_numeric(merged["source_sector_count"], errors="coerce").fillna(0).astype(int)
    merged["has_primary_match"] = merged["match_strategy"].fillna("").astype(str).str.contains("primary", regex=False)
    merged["theme_status"] = merged["theme_status"].fillna("未匹配")
    merged["match_strategy"] = merged["match_strategy"].fillna("no_match")
    merged["used_sectors"] = merged["used_sectors"].fillna("")
    merged["coverage_note"] = merged.apply(
        lambda row: "当前快照命中核心板块。"
        if bool(row["has_primary_match"])
        else ("当前快照仅命中相关板块或未匹配核心板块。" if row["source_count"] else "当前快照中未构建该主题。"),
        axis=1,
    )
    return merged[
        [
            "theme_name",
            "theme_group",
            "main_net_inflow_billion",
            "theme_status",
            "match_strategy",
            "source_count",
            "has_primary_match",
            "used_sectors",
            "taxonomy_primary_count",
            "taxonomy_related_count",
            "coverage_note",
        ]
    ]


def build_overlap_warning_report(taxonomy: dict) -> pd.DataFrame:
    sector_map = build_sector_to_theme_map(taxonomy)
    if sector_map.empty:
        return pd.DataFrame(columns=["sector_name", "theme_names", "overlap_type", "warning_reason"])
    rows = []
    for sector_name, group in sector_map.groupby("sector_name"):
        theme_names = sorted(group["theme_name"].dropna().astype(str).unique())
        roles = set(group["sector_role"].dropna().astype(str))
        if len(theme_names) <= 1:
            continue
        if "primary" in roles and "related" in roles:
            overlap_type = "primary_related_cross"
            reason = f"{sector_name} 同时作为某些主题核心板块和其他主题相关板块，广度观察可能存在交叉。"
        else:
            overlap_type = "multi_theme_sector"
            reason = f"{sector_name} 同时出现在多个主题中，需要注意主题解释边界。"
        rows.append(
            {
                "sector_name": sector_name,
                "theme_names": "，".join(theme_names),
                "overlap_type": overlap_type,
                "warning_reason": reason,
            }
        )
    return pd.DataFrame(rows, columns=["sector_name", "theme_names", "overlap_type", "warning_reason"])


def summarize_coverage_report(report: dict) -> str:
    if not report:
        return "当前暂无主题覆盖审计结果。"
    return str(report.get("coverage_reason") or "当前主题库覆盖情况已生成，可结合未覆盖板块和重复映射继续校准。")
