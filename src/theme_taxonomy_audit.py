from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from src.sample_data import SAMPLE_DIR, build_sample_snapshot_catalog, get_latest_sample_date, load_sample_snapshot_by_date
from src.snapshot_catalog import build_snapshot_catalog, get_latest_snapshot_date, load_snapshot_by_date
from src.theme_taxonomy import (
    build_theme_definition_fingerprint,
    get_taxonomy_themes,
    get_theme_definition,
    get_theme_member_definitions,
    load_theme_taxonomy,
    normalize_taxonomy_name,
    resolve_theme_member_alias,
    validate_theme_taxonomy_structured,
)

OVERLAP_THRESHOLDS = {
    "low_overlap": 0.1,
    "moderate_overlap": 0.25,
    "high_overlap": 0.5,
}

FORBIDDEN_TAXONOMY_AUDIT_WORDS = (
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


def _empty_latest_source(source_mode: str, data_dir: str) -> tuple[str | None, pd.DataFrame]:
    return None, pd.DataFrame(columns=["sector_name"])


def load_source_universe(
    source_mode: str = "SAMPLE",
    data_dir: str | None = None,
    latest_only: bool = True,
) -> tuple[dict, pd.DataFrame]:
    mode = str(source_mode or "SAMPLE").upper()
    if mode == "SAMPLE":
        directory = data_dir or SAMPLE_DIR
        catalog = build_sample_snapshot_catalog(directory)
        latest_date = get_latest_sample_date(catalog)
        df = load_sample_snapshot_by_date(latest_date, sample_dir=directory) if latest_date else pd.DataFrame()
    elif mode == "REAL":
        directory = data_dir or "data/ticks"
        catalog = build_snapshot_catalog(directory)
        latest_date = get_latest_snapshot_date(catalog)
        df = load_snapshot_by_date(latest_date, data_dir=directory) if latest_date else pd.DataFrame()
    else:
        directory = data_dir or ""
        latest_date, df = _empty_latest_source(mode, directory)
    if df is None or df.empty:
        return {
            "source_mode": mode,
            "data_dir": directory,
            "latest_trade_date": latest_date,
            "source_available": False,
            "source_row_count": 0,
            "unique_source_row_count": 0,
        }, pd.DataFrame(columns=["sector_name", "normalized_sector_name"])
    work = df.copy()
    if "sector_type" in work.columns:
        industry = work[work["sector_type"].astype(str).eq("行业资金流")]
        if not industry.empty:
            work = industry
    if latest_only and "captured_time" in work.columns and not work["captured_time"].dropna().empty:
        latest_time = work["captured_time"].dropna().astype(str).max()
        work = work[work["captured_time"].astype(str).eq(latest_time)].copy()
    if "sector_name" not in work.columns:
        work["sector_name"] = ""
    unique = (
        work[["sector_name"]]
        .dropna()
        .assign(sector_name=lambda frame: frame["sector_name"].astype(str).str.strip())
        .query("sector_name != ''")
        .drop_duplicates()
        .reset_index(drop=True)
    )
    unique["normalized_sector_name"] = unique["sector_name"].map(normalize_taxonomy_name)
    return {
        "source_mode": mode,
        "data_dir": directory,
        "latest_trade_date": latest_date,
        "source_available": True,
        "source_row_count": int(len(work)),
        "unique_source_row_count": int(len(unique)),
    }, unique


def classify_overlap_state(jaccard: float) -> str:
    if jaccard <= 0:
        return "none"
    if jaccard >= OVERLAP_THRESHOLDS["high_overlap"]:
        return "high_overlap"
    if jaccard >= OVERLAP_THRESHOLDS["moderate_overlap"]:
        return "moderate_overlap"
    return "low_overlap"


def build_cross_theme_overlap_audit(taxonomy: dict | None = None) -> pd.DataFrame:
    taxonomy = taxonomy or load_theme_taxonomy()
    themes = get_taxonomy_themes(taxonomy)
    rows = []
    member_by_theme = {
        str(theme.get("theme_name") or ""): {
            item["canonical_name"]
            for item in get_theme_member_definitions({"themes": [theme]})
            if item.get("enabled", True) and item.get("canonical_name")
        }
        for theme in themes
    }
    core_by_theme = {
        str(theme.get("theme_name") or ""): {
            item["canonical_name"]
            for item in get_theme_member_definitions({"themes": [theme]})
            if item.get("enabled", True) and item.get("role") == "core"
        }
        for theme in themes
    }
    strict_by_theme = {
        str(theme.get("theme_name") or ""): {
            item["canonical_name"]
            for item in get_theme_member_definitions({"themes": [theme]})
            if item.get("enabled", True) and item.get("strict_representative")
        }
        for theme in themes
    }
    names = [str(theme.get("theme_name") or "") for theme in themes]
    for idx, left in enumerate(names):
        for right in names[idx + 1 :]:
            left_members = member_by_theme.get(left, set())
            right_members = member_by_theme.get(right, set())
            shared = sorted(left_members & right_members)
            union = left_members | right_members
            jaccard = len(shared) / len(union) if union else 0.0
            shared_core = sorted(core_by_theme.get(left, set()) & core_by_theme.get(right, set()))
            shared_strict = sorted(strict_by_theme.get(left, set()) & strict_by_theme.get(right, set()))
            rows.append(
                {
                    "theme_left": left,
                    "theme_right": right,
                    "shared_members": shared,
                    "shared_member_count": len(shared),
                    "member_union_count": len(union),
                    "jaccard_overlap": round(float(jaccard), 4),
                    "shared_core_members": shared_core,
                    "shared_core_count": len(shared_core),
                    "shared_strict_representatives": shared_strict,
                    "shared_strict_count": len(shared_strict),
                    "overlap_state": classify_overlap_state(jaccard),
                }
            )
    return pd.DataFrame(rows)


def build_source_universe_coverage_audit(
    taxonomy: dict | None = None,
    source_mode: str = "SAMPLE",
    data_dir: str | None = None,
) -> dict:
    taxonomy = taxonomy or load_theme_taxonomy()
    source_meta, source_df = load_source_universe(source_mode=source_mode, data_dir=data_dir)
    member_defs = [item for item in get_theme_member_definitions(taxonomy) if item.get("enabled", True)]
    configured_members = {item["canonical_name"] for item in member_defs if item.get("canonical_name")}
    if source_df.empty:
        return {
            **source_meta,
            "mapped_source_row_count": 0,
            "ambiguous_source_row_count": 0,
            "unmapped_source_row_count": 0,
            "mapping_coverage_rate": 0.0,
            "canonical_exact_match_count": 0,
            "alias_match_count": 0,
            "themes_represented": [],
            "themes_with_zero_matched_members": sorted({str(theme.get("theme_name") or "") for theme in get_taxonomy_themes(taxonomy)}),
            "configured_members_absent_count": len(configured_members),
            "configured_members_absent": sorted(configured_members),
            "unmapped_source_rows": [],
            "ambiguous_source_rows": [],
            "denominator_note": "mapping_coverage_rate = mapped unique normalized source rows / total unique normalized source rows.",
        }
    mapped = []
    ambiguous = []
    unmapped = []
    canonical_exact = 0
    alias_match = 0
    themes_represented: set[str] = set()
    matched_members: set[str] = set()
    for row in source_df.to_dict(orient="records"):
        result = resolve_theme_member_alias(row.get("sector_name"), taxonomy)
        status = result.get("ambiguity_status")
        if status == "resolved":
            mapped.append({**row, **result})
            matched_members.add(str(result.get("canonical_member")))
            themes_represented.update(result.get("candidate_themes") or [])
            if result.get("matched_by") == "canonical_exact":
                canonical_exact += 1
            elif result.get("matched_by") == "explicit_alias":
                alias_match += 1
        elif status == "ambiguous":
            ambiguous.append({**row, **result})
            themes_represented.update(result.get("candidate_themes") or [])
        else:
            unmapped.append(row)
    total = int(len(source_df))
    mapped_count = int(len(mapped))
    return {
        **source_meta,
        "mapped_source_row_count": mapped_count,
        "ambiguous_source_row_count": int(len(ambiguous)),
        "unmapped_source_row_count": int(len(unmapped)),
        "mapping_coverage_rate": round(mapped_count / total, 4) if total else 0.0,
        "canonical_exact_match_count": canonical_exact,
        "alias_match_count": alias_match,
        "themes_represented": sorted(themes_represented),
        "themes_with_zero_matched_members": sorted({str(theme.get("theme_name") or "") for theme in get_taxonomy_themes(taxonomy)} - themes_represented),
        "configured_members_absent_count": len(configured_members - matched_members),
        "configured_members_absent": sorted(configured_members - matched_members),
        "unmapped_source_rows": unmapped[:40],
        "ambiguous_source_rows": ambiguous[:40],
        "denominator_note": "mapping_coverage_rate = mapped unique normalized source rows / total unique normalized source rows.",
    }


def build_theme_calibration_report(
    taxonomy: dict | None = None,
    source_mode: str = "SAMPLE",
    data_dir: str | None = None,
) -> pd.DataFrame:
    taxonomy = taxonomy or load_theme_taxonomy()
    _, source_df = load_source_universe(source_mode=source_mode, data_dir=data_dir)
    source_names = set(source_df["normalized_sector_name"].tolist()) if not source_df.empty else set()
    overlap_df = build_cross_theme_overlap_audit(taxonomy)
    member_to_themes: dict[str, set[str]] = defaultdict(set)
    strict_to_themes: dict[str, set[str]] = defaultdict(set)
    for member in get_theme_member_definitions(taxonomy):
        if not member.get("enabled", True):
            continue
        member_to_themes[member["canonical_name"]].add(member["theme_name"])
        if member.get("strict_representative"):
            strict_to_themes[member["canonical_name"]].add(member["theme_name"])
    rows = []
    for theme in get_taxonomy_themes(taxonomy):
        theme_name = str(theme.get("theme_name") or "")
        members = [item for item in get_theme_member_definitions({"themes": [theme]}) if item.get("enabled", True)]
        matched = [item["canonical_name"] for item in members if item.get("normalized_canonical_name") in source_names]
        unmatched = [item["canonical_name"] for item in members if item.get("normalized_canonical_name") not in source_names]
        related_overlap = overlap_df[
            (overlap_df["theme_left"].eq(theme_name) | overlap_df["theme_right"].eq(theme_name))
            & overlap_df["shared_member_count"].gt(0)
        ].copy()
        if not related_overlap.empty:
            related_overlap["neighbor"] = related_overlap.apply(
                lambda row: row["theme_right"] if row["theme_left"] == theme_name else row["theme_left"],
                axis=1,
            )
            top_neighbors = related_overlap.sort_values(["jaccard_overlap", "shared_member_count"], ascending=False)["neighbor"].head(3).tolist()
        else:
            top_neighbors = []
        provenance_counts = dict(Counter(item.get("mapping_method") or "unknown" for item in members))
        reused = sorted([member for member in {item["canonical_name"] for item in members} if len(member_to_themes.get(member, set())) > 1])
        reused_strict = sorted([member for member in {item["canonical_name"] for item in members if item.get("strict_representative")} if len(strict_to_themes.get(member, set())) > 1])
        rows.append(
            {
                "theme_name": theme_name,
                "theme_definition_fingerprint": build_theme_definition_fingerprint(theme),
                "member_count": len(members),
                "core_count": sum(1 for item in members if item.get("role") == "core"),
                "related_count": sum(1 for item in members if item.get("role") == "related"),
                "strict_representative_count": sum(1 for item in members if item.get("strict_representative")),
                "member_provenance_counts": provenance_counts,
                "matched_member_count": len(matched),
                "unmatched_member_count": len(unmatched),
                "matched_members": matched,
                "unmatched_members": unmatched,
                "reused_members": reused,
                "reused_strict_representatives": reused_strict,
                "highest_overlap_neighbors": top_neighbors,
                "warnings": [
                    *([f"{len(unmatched)} configured members absent from {str(source_mode).upper()} universe."] if unmatched else []),
                    *([f"reused members: {', '.join(reused)}"] if reused else []),
                ],
            }
        )
    return pd.DataFrame(rows)


def build_taxonomy_audit_report(
    taxonomy: dict | None = None,
    source_mode: str = "SAMPLE",
    data_dir: str | None = None,
) -> dict:
    taxonomy = taxonomy or load_theme_taxonomy()
    members = [item for item in get_theme_member_definitions(taxonomy) if item.get("enabled", True)]
    validation = validate_theme_taxonomy_structured(taxonomy)
    overlap_df = build_cross_theme_overlap_audit(taxonomy)
    coverage = build_source_universe_coverage_audit(taxonomy, source_mode=source_mode, data_dir=data_dir)
    calibration_df = build_theme_calibration_report(taxonomy, source_mode=source_mode, data_dir=data_dir)
    member_counts = Counter(item["canonical_name"] for item in members)
    strict_counts = Counter(item["canonical_name"] for item in members if item.get("strict_representative"))
    top_overlap = (
        overlap_df.sort_values(["jaccard_overlap", "shared_member_count"], ascending=False).head(10).to_dict(orient="records")
        if not overlap_df.empty
        else []
    )
    return {
        "taxonomy_name": taxonomy.get("taxonomy_name"),
        "taxonomy_version": taxonomy.get("version"),
        "source_mode": str(source_mode or "SAMPLE").upper(),
        "theme_count": len(get_taxonomy_themes(taxonomy)),
        "member_assignment_count": len(members),
        "unique_canonical_member_count": len({item["canonical_name"] for item in members}),
        "reused_members": {member: count for member, count in sorted(member_counts.items()) if count > 1},
        "reused_strict_representatives": {member: count for member, count in sorted(strict_counts.items()) if count > 1},
        "validation": validation,
        "coverage": coverage,
        "top_overlap_pairs": top_overlap,
        "calibration": calibration_df.to_dict(orient="records") if not calibration_df.empty else [],
        "overlap_thresholds": OVERLAP_THRESHOLDS,
        "audit_label": "taxonomy audit 可用" if validation.get("error_count", 0) == 0 else "taxonomy audit 存在结构错误",
        "audit_reason": "该审计只解释主题语义映射、重叠和 source-universe 覆盖，不代表正式行业分类或投资判断。",
    }


def validate_taxonomy_audit_text(text: str) -> list[str]:
    value = str(text or "")
    return [word for word in FORBIDDEN_TAXONOMY_AUDIT_WORDS if word in value]
