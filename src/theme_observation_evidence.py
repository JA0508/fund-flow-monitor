from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from src.history_evidence import (
    build_historical_evidence_dimensions,
    build_historical_coverage_summary,
    build_snapshot_manifest,
    classify_historical_evidence_readiness,
    resolve_replay_evidence,
)
from src.sample_data import SAMPLE_DIR, build_sample_snapshot_catalog, get_latest_sample_date, load_sample_snapshot_by_date
from src.snapshot_catalog import build_snapshot_catalog, get_latest_snapshot_date, load_snapshot_by_date
from src.theme_pool import build_theme_snapshot_with_trace
from src.theme_taxonomy import build_theme_definition_evidence, load_theme_taxonomy


FORBIDDEN_THEME_EVIDENCE_WORDS = (
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


MODE_LABELS = {
    "strict_representative": "严格代表口径",
    "representative": "代表口径",
    "breadth": "广度观察",
}


def _stable_id(payload: dict, length: int = 20) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _safe_latest_value(df: pd.DataFrame, column: str) -> str | None:
    if df is None or df.empty or column not in df.columns:
        return None
    values = df[column].dropna().astype(str)
    values = values[values.str.strip().ne("")]
    if values.empty:
        return None
    return str(values.iloc[-1])


def normalize_theme_evidence_mode(mode: str | None) -> str:
    value = str(mode or "").strip()
    if value in MODE_LABELS:
        return value
    reverse = {label: key for key, label in MODE_LABELS.items()}
    return reverse.get(value, "strict_representative")


def _select_data_dir(source_mode: str, data_dir: str | None = None) -> str:
    if data_dir:
        return data_dir
    return SAMPLE_DIR if str(source_mode or "").upper() == "SAMPLE" else "data/ticks"


def _latest_date_for_source(source_mode: str, data_dir: str) -> str | None:
    if str(source_mode or "").upper() == "SAMPLE":
        return get_latest_sample_date(build_sample_snapshot_catalog(data_dir))
    return get_latest_snapshot_date(build_snapshot_catalog(data_dir))


def _load_source_snapshot(source_mode: str, trade_date: str, data_dir: str) -> pd.DataFrame:
    if str(source_mode or "").upper() == "SAMPLE":
        return load_sample_snapshot_by_date(trade_date, sample_dir=data_dir)
    return load_snapshot_by_date(trade_date, data_dir=data_dir)


def _latest_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    if "sector_type" in work.columns:
        industry = work[work["sector_type"].astype(str).eq("行业资金流")]
        if not industry.empty:
            work = industry
    if "captured_at" in work.columns:
        parsed = pd.to_datetime(work["captured_at"], errors="coerce")
        valid = work[parsed.notna()].copy()
        if not valid.empty:
            latest_at = parsed[parsed.notna()].max()
            return valid[pd.to_datetime(valid["captured_at"], errors="coerce").eq(latest_at)].copy()
    if "captured_time" in work.columns:
        latest_time = work["captured_time"].dropna().astype(str).max()
        if latest_time:
            return work[work["captured_time"].astype(str).eq(str(latest_time))].copy()
    return work.copy()


def build_theme_data_evidence(
    manifest_df: pd.DataFrame | None,
    selected_trade_date: str | None = None,
    source_mode: str = "REAL",
) -> dict:
    summary = build_historical_coverage_summary(manifest_df)
    readiness = classify_historical_evidence_readiness(summary)
    dimensions = build_historical_evidence_dimensions(summary)
    replay = resolve_replay_evidence(selected_trade_date, manifest_df, source_mode=source_mode) if selected_trade_date else {}
    warnings = []
    if str(source_mode or "").upper() == "SAMPLE":
        warnings.append("当前证据来自 SAMPLE 合成演示数据，不代表真实行情。")
    if dimensions.get("intraday_depth_state") in {"no_intraday_depth", "single_point_per_date", "sparse_intraday"}:
        warnings.append(dimensions.get("intraday_depth_reason", "日内覆盖有限。"))
    if dimensions.get("coverage_consistency_state") == "uneven":
        warnings.append(dimensions.get("coverage_consistency_reason", "历史覆盖不均衡。"))
    return {
        "source_mode": str(source_mode or "REAL").upper(),
        "snapshot_count_represented": int(summary.get("valid_snapshot_count", 0) or 0),
        "trade_date_count": int(summary.get("trade_date_count", 0) or 0),
        "trade_date_start": summary.get("earliest_trade_date"),
        "trade_date_end": summary.get("latest_trade_date"),
        "provider_counts": summary.get("provider_counts", {}),
        "api_counts": summary.get("api_counts", {}),
        "schema_fingerprints": sorted((summary.get("schema_fingerprint_counts") or {}).keys()),
        "schema_consistent": bool(summary.get("schema_consistent")),
        "readiness_state": readiness.get("readiness_state"),
        "readiness_label": readiness.get("readiness_label"),
        "history_span_state": dimensions.get("history_span_state"),
        "intraday_depth_state": dimensions.get("intraday_depth_state"),
        "coverage_consistency_state": dimensions.get("coverage_consistency_state"),
        "history_span_label": dimensions.get("history_span_label"),
        "intraday_depth_label": dimensions.get("intraday_depth_label"),
        "coverage_consistency_label": dimensions.get("coverage_consistency_label"),
        "replay_evidence": replay,
        "warnings": warnings,
    }


def build_theme_observation_evidence(
    latest_df: pd.DataFrame,
    theme_name: str,
    theme_mode: str = "strict_representative",
    taxonomy: dict | None = None,
    source_mode: str = "REAL",
    manifest_df: pd.DataFrame | None = None,
    as_of_trade_date: str | None = None,
    as_of_captured_time: str | None = None,
    taxonomy_source: str = "config/theme_taxonomy.json",
) -> dict:
    source_mode = str(source_mode or "REAL").upper()
    mode = normalize_theme_evidence_mode(theme_mode)
    taxonomy = taxonomy or load_theme_taxonomy()
    theme_df, trace_map = build_theme_snapshot_with_trace(latest_df, theme_mode=mode)
    trace = trace_map.get(str(theme_name or ""))
    definition = build_theme_definition_evidence(taxonomy, theme_name, taxonomy_source=taxonomy_source)
    as_of_trade_date = as_of_trade_date or _safe_latest_value(latest_df, "trade_date")
    as_of_captured_time = as_of_captured_time or _safe_latest_value(latest_df, "captured_time")
    data_evidence = build_theme_data_evidence(manifest_df, selected_trade_date=as_of_trade_date, source_mode=source_mode)
    warnings = list(data_evidence.get("warnings", []))
    if not trace:
        warnings.append("当前快照未生成该主题的主题观察结果。")
    else:
        unmatched = int(trace.get("unmatched_member_count", 0) or 0)
        if unmatched:
            warnings.append(f"有 {unmatched} 个配置成员在当前快照中未匹配。")
    observation_id = _stable_id(
        {
            "theme": str(theme_name or ""),
            "mode": mode,
            "source_mode": source_mode,
            "trade_date": as_of_trade_date,
            "captured_time": as_of_captured_time,
            "taxonomy": definition.get("taxonomy_fingerprint"),
            "definition": definition.get("theme_definition_fingerprint"),
            "aggregate": None if not trace else trace.get("aggregate_value"),
        }
    )
    canonical_row = trace.get("canonical_row", {}) if trace else {}
    return {
        "observation_id": observation_id,
        "theme_name": str(theme_name or ""),
        "theme_id": definition.get("theme_id") or str(theme_name or ""),
        "observation_mode": mode,
        "observation_mode_label": MODE_LABELS.get(mode, mode),
        "source_mode": source_mode,
        "as_of_trade_date": as_of_trade_date,
        "as_of_captured_time": as_of_captured_time,
        "taxonomy_fingerprint": definition.get("taxonomy_fingerprint"),
        "theme_definition_fingerprint": definition.get("theme_definition_fingerprint"),
        "taxonomy_version": definition.get("taxonomy_version"),
        "theme_definition": definition,
        "calculation_scope": mode,
        "configured_core_members": definition.get("core_members", []),
        "configured_related_members": definition.get("related_members", []),
        "matched_member_count": int(trace.get("matched_member_count", 0) if trace else 0),
        "unmatched_member_count": int(trace.get("unmatched_member_count", 0) if trace else len(definition.get("core_members", [])) + len(definition.get("related_members", []))),
        "used_member_count": int(trace.get("used_member_count", 0) if trace else 0),
        "member_traces": trace.get("all_members", []) if trace else [],
        "matched_members": trace.get("matched_members", []) if trace else [],
        "aggregation_method": trace.get("aggregation_method") if trace else None,
        "aggregation_inputs": trace.get("aggregation_inputs", []) if trace else [],
        "aggregate_value": trace.get("aggregate_value") if trace else None,
        "thresholds_used": trace.get("thresholds", []) if trace else [],
        "derived_state": trace.get("derived_state") if trace else None,
        "derived_state_level": trace.get("derived_state_level") if trace else None,
        "match_strategy": trace.get("match_strategy") if trace else None,
        "theme_value_label": trace.get("theme_value_label") if trace else None,
        "canonical_theme_row": canonical_row,
        "data_evidence": data_evidence,
        "warnings": warnings,
        "evidence_available": bool(trace),
    }


def resolve_theme_observation_evidence(
    theme_name: str,
    source_mode: str = "SAMPLE",
    theme_mode: str = "strict_representative",
    trade_date: str | None = None,
    data_dir: str | None = None,
    taxonomy: dict | None = None,
) -> dict:
    source_mode = str(source_mode or "SAMPLE").upper()
    taxonomy = taxonomy or load_theme_taxonomy()
    known_themes = {
        str(item.get("theme_name", "")).strip()
        for item in taxonomy.get("themes", [])
        if isinstance(item, dict) and str(item.get("theme_name", "")).strip()
    }
    if theme_name not in known_themes:
        return {
            "evidence_available": False,
            "source_mode": source_mode,
            "theme_name": theme_name,
            "warnings": [f"未知主题：{theme_name}。"],
        }
    if source_mode not in {"SAMPLE", "REAL"}:
        return {
            "evidence_available": False,
            "source_mode": source_mode,
            "theme_name": theme_name,
            "warnings": ["source_mode 仅支持 SAMPLE 或 REAL，未执行查询。"],
        }
    data_dir = _select_data_dir(source_mode, data_dir)
    selected_date = trade_date or _latest_date_for_source(source_mode, data_dir)
    manifest = build_snapshot_manifest(data_dir, source_mode=source_mode)
    if not selected_date:
        return {
            "evidence_available": False,
            "source_mode": source_mode,
            "theme_name": theme_name,
            "warnings": ["当前目录没有可用快照日期。"],
            "data_evidence": build_theme_data_evidence(manifest, source_mode=source_mode),
        }
    ticks = _load_source_snapshot(source_mode, selected_date, data_dir)
    latest = _latest_frame(ticks)
    if latest.empty:
        return {
            "evidence_available": False,
            "source_mode": source_mode,
            "theme_name": theme_name,
            "as_of_trade_date": selected_date,
            "warnings": [f"日期 {selected_date} 没有可用行业资金流快照。"],
            "data_evidence": build_theme_data_evidence(manifest, selected_trade_date=selected_date, source_mode=source_mode),
        }
    return build_theme_observation_evidence(
        latest,
        theme_name=theme_name,
        theme_mode=theme_mode,
        taxonomy=taxonomy,
        source_mode=source_mode,
        manifest_df=manifest,
        as_of_trade_date=selected_date,
    )


def build_theme_evidence_contribution_table(evidence: dict) -> pd.DataFrame:
    rows = evidence.get("member_traces", []) if evidence else []
    if not rows:
        return pd.DataFrame()
    columns = [
        "member_name",
        "canonical_member",
        "member_role",
        "match_type",
        "matched_by",
        "alias_used",
        "ambiguity_status",
        "matched_source_row",
        "normalized_source_row",
        "input_value",
        "included",
        "strict_representative",
        "mapping_source",
        "mapping_method",
        "mapping_rationale",
        "exclusion_reason",
    ]
    frame = pd.DataFrame(rows)
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]


def build_theme_research_snapshot(evidence: dict | None) -> dict:
    """Turn existing theme evidence into a concise, non-predictive research readout."""
    evidence = evidence or {}
    data_evidence = evidence.get("data_evidence") or {}
    source_mode = str(evidence.get("source_mode") or "REAL").upper()
    warnings = [str(item) for item in evidence.get("warnings") or [] if str(item).strip()]
    if source_mode == "SAMPLE":
        source_notice = "当前主题观察来自 SAMPLE 合成演示数据，不代表真实行情。"
        warnings = [item for item in warnings if "当前证据来自 SAMPLE 合成演示数据" not in item]
    else:
        source_notice = "当前主题观察仅基于已导入 CSV 快照；CSV 是主数据来源。"

    if not evidence.get("evidence_available"):
        return {
            "research_snapshot_available": False,
            "theme_name": str(evidence.get("theme_name") or "所选主题"),
            "source_mode": source_mode,
            "observed_state": "暂无主题观察",
            "aggregate_value": None,
            "member_coverage_label": "当前没有可用于聚合的主题成员证据。",
            "history_readiness_label": data_evidence.get("readiness_label") or "历史证据状态未知",
            "history_scope_notice": "快照覆盖只说明已导入 CSV 的可回放范围，不等同于 contract-qualified 多日历史。",
            "source_notice": source_notice,
            "limitations": warnings or ["当前主题缺少可用快照或成员匹配证据。"],
        }

    configured_count = len(evidence.get("configured_core_members") or []) + len(
        evidence.get("configured_related_members") or []
    )
    matched_count = int(evidence.get("matched_member_count", 0) or 0)
    used_count = int(evidence.get("used_member_count", 0) or 0)
    return {
        "research_snapshot_available": True,
        "theme_name": str(evidence.get("theme_name") or "所选主题"),
        "source_mode": source_mode,
        "as_of_trade_date": evidence.get("as_of_trade_date"),
        "as_of_captured_time": evidence.get("as_of_captured_time"),
        "observation_mode_label": evidence.get("observation_mode_label") or "--",
        "observed_state": evidence.get("derived_state") or "状态未映射",
        "aggregate_value": evidence.get("aggregate_value"),
        "member_coverage_label": f"当前快照匹配 {matched_count}/{configured_count} 个配置成员；参与聚合 {used_count} 个。",
        "history_readiness_label": data_evidence.get("readiness_label") or "历史证据状态未知",
        "history_scope_notice": "快照覆盖只说明已导入 CSV 的可回放范围，不等同于 contract-qualified 多日历史。",
        "source_notice": source_notice,
        "limitations": warnings,
    }


def render_theme_research_snapshot_section(evidence: dict | None, heading_level: int = 2) -> str:
    """Render the existing observation evidence as a concise brief section."""
    hashes = "#" * max(1, min(heading_level, 4))
    snapshot = build_theme_research_snapshot(evidence)
    lines = [f"{hashes} 主题观察结论", ""]
    if not snapshot["research_snapshot_available"]:
        lines.extend(
            [
                f"- 主题：{snapshot['theme_name']}",
                "- 当前状态：暂无主题观察。",
                f"- 观察限制：{'；'.join(snapshot['limitations'])}",
                f"- 数据说明：{snapshot['source_notice']}",
                "- 本段只描述已有快照证据，不预测未来走势，不构成投资建议。",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            f"- 主题：{snapshot['theme_name']}",
            f"- 观察日期 / 时间：{snapshot.get('as_of_trade_date') or '--'} / {snapshot.get('as_of_captured_time') or '--'}",
            f"- 主题口径：{snapshot.get('observation_mode_label') or '--'}",
            f"- 当前状态：{snapshot['observed_state']}",
            f"- 成员覆盖：{snapshot['member_coverage_label']}",
            f"- 快照覆盖：{snapshot['history_readiness_label']}",
            f"- 资格说明：{snapshot['history_scope_notice']}",
            f"- 数据说明：{snapshot['source_notice']}",
        ]
    )
    if snapshot["limitations"]:
        lines.append(f"- 观察限制：{'；'.join(snapshot['limitations'][:3])}")
    lines.append("- 本段只描述已有快照证据，不预测未来走势，不构成投资建议。")
    return "\n".join(lines)


def render_theme_extended_evidence_unavailable_section(theme_name: str | None, heading_level: int = 2) -> str:
    """Record an unavailable optional evidence layer without exposing internal errors."""
    hashes = "#" * max(1, min(heading_level, 4))
    theme = str(theme_name or "所选主题")
    return "\n".join(
        [
            f"{hashes} 扩展主题证据状态",
            "",
            f"- 主题：{theme}",
            "- 部分扩展证据（主题动态、结构状态或主题关系）本次未能生成。",
            "- 基础主题观察、成员覆盖和数据来源口径仍保留；缺失的扩展证据不会被视为支持性结论。",
            "- 本段只说明已生成证据的边界，不预测未来走势，不构成投资建议。",
        ]
    )


def render_theme_evidence_markdown(evidence: dict, heading_level: int = 2) -> str:
    hashes = "#" * max(1, min(heading_level, 4))
    if not evidence or not evidence.get("evidence_available"):
        theme = (evidence or {}).get("theme_name") or "所选主题"
        return f"{hashes} 主题状态证据\n\n{theme} 暂无可用主题证据。"
    data = evidence.get("data_evidence", {})
    lines = [
        f"{hashes} 主题状态证据",
        "",
        f"- 主题：{evidence.get('theme_name')}",
        f"- 来源：{evidence.get('source_mode')}",
        f"- 口径：{evidence.get('observation_mode_label')}",
        f"- 日期 / 时间：{evidence.get('as_of_trade_date') or '--'} / {evidence.get('as_of_captured_time') or '--'}",
        f"- taxonomy fingerprint：`{str(evidence.get('taxonomy_fingerprint') or '')[:12]}`",
        f"- theme definition fingerprint：`{str(evidence.get('theme_definition_fingerprint') or '')[:12]}`",
        f"- 聚合方法：{evidence.get('aggregation_method')}",
        f"- 聚合值：{evidence.get('aggregate_value')}",
        f"- 状态映射：{evidence.get('derived_state')}",
        f"- 历史覆盖：{data.get('history_span_label') or '--'} / {data.get('intraday_depth_label') or '--'} / {data.get('coverage_consistency_label') or '--'}",
    ]
    if evidence.get("source_mode") == "SAMPLE":
        lines.append("- SAMPLE 说明：当前证据来自合成演示数据，不代表真实行情。")
    lines.append("- 本段只描述计算 lineage 和已导入快照证据，不预测未来走势，不构成投资建议。")
    return "\n".join(lines)


def render_brief_provenance_section(evidence: dict, heading_level: int = 2) -> str:
    hashes = "#" * max(1, min(heading_level, 4))
    if not evidence:
        return f"{hashes} 简报证据口径\n\n暂无可用主题证据口径。"
    data = evidence.get("data_evidence", {})
    lines = [
        f"{hashes} 简报证据口径",
        "",
        f"- 来源模式：{evidence.get('source_mode') or '--'}",
        f"- 观察日期 / 时间：{evidence.get('as_of_trade_date') or '--'} / {evidence.get('as_of_captured_time') or '--'}",
        f"- 主题计算口径：{evidence.get('observation_mode_label') or '--'}",
        f"- 代表主题证据：{evidence.get('theme_name') or '--'}",
        f"- taxonomy fingerprint：`{str(evidence.get('taxonomy_fingerprint') or '')[:12]}`",
        f"- schema consistent：{data.get('schema_consistent')}",
        f"- 历史覆盖状态：{data.get('history_span_state') or '--'} / {data.get('intraday_depth_state') or '--'} / {data.get('coverage_consistency_state') or '--'}",
    ]
    if evidence.get("source_mode") == "SAMPLE":
        lines.append("- SAMPLE 说明：本简报中的主题证据来自合成演示数据，不代表真实行情。")
    lines.append("- 该口径只用于说明数据来源和计算 lineage，不预测未来走势，不构成投资建议。")
    return "\n".join(lines)


def validate_theme_evidence_text(text: str) -> list[str]:
    value = str(text or "")
    return [word for word in FORBIDDEN_THEME_EVIDENCE_WORDS if word in value]
