from __future__ import annotations

from collections import Counter
from typing import Iterable

import pandas as pd

from src.analytical_continuity import (
    CONTINUITY_SEGMENT_COLUMN,
    RESOLUTION_EXPLICIT_ID_ONLY,
    RESOLUTION_EXPLICIT_VERIFIED,
    RESOLUTION_INFERRED,
    RESOLUTION_SAMPLE_SYNTHETIC,
    RESOLUTION_UNKNOWN,
    attach_continuity_columns,
)
from src.provider_comparability import compare_provider_contracts
from src.provider_contracts import UNKNOWN, build_provider_contract_short_id
from src.provider_registry import get_primary_provider_contract, list_provider_contracts


WORKLOAD_REPLAY_INSPECTION = "replay_inspection"
WORKLOAD_THEME_DESCRIPTIVE = "theme_descriptive_observation"
WORKLOAD_THEME_CONTINUITY = "theme_continuity_analysis"
WORKLOAD_REGIME = "regime_analysis"
WORKLOAD_RELATIONSHIP = "relationship_analysis"
WORKLOAD_ROBUSTNESS = "robustness_analysis"
WORKLOAD_OBSERVATION_BRIEF = "observation_brief"

DESCRIPTIVE_WORKLOADS = (WORKLOAD_REPLAY_INSPECTION, WORKLOAD_THEME_DESCRIPTIVE)
QUALIFIED_WORKLOADS = (
    WORKLOAD_THEME_CONTINUITY,
    WORKLOAD_REGIME,
    WORKLOAD_RELATIONSHIP,
    WORKLOAD_ROBUSTNESS,
    WORKLOAD_OBSERVATION_BRIEF,
)
ANALYTICAL_WORKLOADS = DESCRIPTIVE_WORKLOADS + QUALIFIED_WORKLOADS

ELIGIBILITY_ELIGIBLE = "eligible"
ELIGIBILITY_DESCRIPTIVE = "descriptive_eligible"
ELIGIBILITY_EXCLUDED = "excluded"

REASON_DESCRIPTIVE = "workload_allows_readable_descriptive_history"
REASON_REAL_PRIMARY_VERIFIED = "explicit_verified_primary_contract"
REASON_SAMPLE_DEMO = "sample_synthetic_demo_eligible"
REASON_UNRESOLVED = "unresolved_provider_contract"
REASON_EXPLICIT_ID_ONLY = "explicit_id_only_without_fingerprint"
REASON_INFERRED = "inferred_contract_not_explicitly_verified"
REASON_INCOMPLETE = "contract_identity_incomplete"
REASON_NOT_PRIMARY = "contract_not_primary_or_equivalent"
REASON_SAMPLE_NOT_REAL = "sample_not_real_qualified_history"
REASON_SOURCE_UNSUPPORTED = "unsupported_source_mode"

READINESS_NO_HISTORY = "no_qualified_history"
READINESS_SINGLE_SNAPSHOT = "single_qualified_snapshot"
READINESS_SINGLE_DATE = "single_qualified_date"
READINESS_LIMITED_MULTI_DAY = "limited_qualified_multi_day"
READINESS_READY = "qualified_multi_day_ready"

FORBIDDEN_ANALYTICAL_ELIGIBILITY_WORDS = (
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
    "confidence score",
    "readiness score",
    "probability",
)


def _clean(value: object, fallback: str = UNKNOWN) -> str:
    if value is None:
        return fallback
    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "null"}:
        return fallback
    return text


def get_analytical_workload_options() -> list[str]:
    return list(ANALYTICAL_WORKLOADS)


def normalize_analytical_workload(workload: str | None) -> str:
    value = str(workload or "").strip()
    return value if value in ANALYTICAL_WORKLOADS else WORKLOAD_THEME_CONTINUITY


def _accepted_real_contracts() -> dict[str, str]:
    primary = get_primary_provider_contract()
    accepted = {build_provider_contract_short_id(primary): primary.to_dict()["semantic_contract_id"]}
    for item in list_provider_contracts(include_primary=False):
        comparison = compare_provider_contracts(primary, item)
        if comparison.get("comparability_state") == "equivalent":
            accepted[build_provider_contract_short_id(item)] = str(item.get("semantic_contract_id") or "")
    return accepted


def _is_real_contract_explicit_verified(row: dict) -> tuple[bool, str]:
    contract_id = _clean(row.get("provider_contract_id"), "")
    fingerprint = _clean(row.get("provider_contract_fingerprint"), "")
    state = _clean(row.get("provider_contract_resolution_state"), RESOLUTION_UNKNOWN)
    if state == RESOLUTION_UNKNOWN:
        return False, REASON_UNRESOLVED
    if state == RESOLUTION_INFERRED:
        return False, REASON_INFERRED
    if state == RESOLUTION_EXPLICIT_ID_ONLY:
        return False, REASON_EXPLICIT_ID_ONLY
    if state != RESOLUTION_EXPLICIT_VERIFIED:
        return False, REASON_INCOMPLETE
    if not contract_id or contract_id == UNKNOWN or not fingerprint or fingerprint == UNKNOWN:
        return False, REASON_INCOMPLETE
    accepted = _accepted_real_contracts()
    expected_fp = accepted.get(contract_id)
    if not expected_fp or expected_fp != fingerprint:
        return False, REASON_NOT_PRIMARY
    return True, REASON_REAL_PRIMARY_VERIFIED


def evaluate_observation_eligibility(
    row: dict | pd.Series,
    workload: str | None = WORKLOAD_THEME_CONTINUITY,
) -> dict:
    workload_name = normalize_analytical_workload(workload)
    data = row.to_dict() if isinstance(row, pd.Series) else dict(row or {})
    source = _clean(data.get("source_mode") or data.get("data_mode"), UNKNOWN).upper()
    continuity_segment = _clean(data.get(CONTINUITY_SEGMENT_COLUMN), UNKNOWN)
    contract_id = _clean(data.get("provider_contract_id"), UNKNOWN)
    resolution = _clean(data.get("provider_contract_resolution_state"), RESOLUTION_UNKNOWN)
    fingerprint = _clean(data.get("provider_contract_fingerprint"), UNKNOWN)

    if workload_name in DESCRIPTIVE_WORKLOADS:
        return {
            "analytical_workload": workload_name,
            "analytical_eligibility_state": ELIGIBILITY_DESCRIPTIVE,
            "is_analytically_eligible": True,
            "analytical_eligibility_reason": REASON_DESCRIPTIVE,
            "qualified_source_scope": "descriptive_readable_history",
            "source_mode": source,
            CONTINUITY_SEGMENT_COLUMN: continuity_segment,
            "provider_contract_id": contract_id,
            "provider_contract_fingerprint": fingerprint,
            "provider_contract_resolution_state": resolution,
        }

    if source == "SAMPLE":
        eligible = resolution == RESOLUTION_SAMPLE_SYNTHETIC
        return {
            "analytical_workload": workload_name,
            "analytical_eligibility_state": ELIGIBILITY_ELIGIBLE if eligible else ELIGIBILITY_EXCLUDED,
            "is_analytically_eligible": bool(eligible),
            "analytical_eligibility_reason": REASON_SAMPLE_DEMO if eligible else REASON_SAMPLE_NOT_REAL,
            "qualified_source_scope": "sample_demo_analytics" if eligible else "excluded",
            "source_mode": source,
            CONTINUITY_SEGMENT_COLUMN: continuity_segment,
            "provider_contract_id": contract_id,
            "provider_contract_fingerprint": fingerprint,
            "provider_contract_resolution_state": resolution,
        }

    if source == "REAL":
        eligible, reason = _is_real_contract_explicit_verified(data)
        return {
            "analytical_workload": workload_name,
            "analytical_eligibility_state": ELIGIBILITY_ELIGIBLE if eligible else ELIGIBILITY_EXCLUDED,
            "is_analytically_eligible": bool(eligible),
            "analytical_eligibility_reason": reason,
            "qualified_source_scope": "real_contract_qualified" if eligible else "excluded",
            "source_mode": source,
            CONTINUITY_SEGMENT_COLUMN: continuity_segment,
            "provider_contract_id": contract_id,
            "provider_contract_fingerprint": fingerprint,
            "provider_contract_resolution_state": resolution,
        }

    return {
        "analytical_workload": workload_name,
        "analytical_eligibility_state": ELIGIBILITY_EXCLUDED,
        "is_analytically_eligible": False,
        "analytical_eligibility_reason": REASON_SOURCE_UNSUPPORTED,
        "qualified_source_scope": "excluded",
        "source_mode": source,
        CONTINUITY_SEGMENT_COLUMN: continuity_segment,
        "provider_contract_id": contract_id,
        "provider_contract_fingerprint": fingerprint,
        "provider_contract_resolution_state": resolution,
    }


def attach_analytical_eligibility(
    df: pd.DataFrame | None,
    workload: str | None = WORKLOAD_THEME_CONTINUITY,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()
    work = attach_continuity_columns(df)
    records = [evaluate_observation_eligibility(row, workload=workload) for _, row in work.iterrows()]
    eligibility = pd.DataFrame(records, index=work.index)
    for column in (
        "analytical_workload",
        "analytical_eligibility_state",
        "is_analytically_eligible",
        "analytical_eligibility_reason",
        "qualified_source_scope",
    ):
        work[column] = eligibility[column]
    return work


def filter_eligible_observations(
    df: pd.DataFrame | None,
    workload: str | None = WORKLOAD_THEME_CONTINUITY,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = attach_analytical_eligibility(df, workload=workload)
    return work[work["is_analytically_eligible"].fillna(False).astype(bool)].copy().reset_index(drop=True)


def _value_counts(df: pd.DataFrame, column: str) -> dict[str, int]:
    if df is None or df.empty or column not in df.columns:
        return {}
    return {str(k): int(v) for k, v in df[column].fillna(UNKNOWN).astype(str).value_counts().to_dict().items()}


def classify_qualified_analytical_readiness(
    summary: dict,
    min_qualified_dates: int = 3,
) -> dict:
    eligible_count = int(summary.get("eligible_observation_count", 0) or 0)
    date_count = int(summary.get("eligible_trade_date_count", 0) or 0)
    if eligible_count <= 0:
        state = READINESS_NO_HISTORY
        label = "暂无 contract-qualified 历史"
        reason = "当前可读历史中没有符合该 workload 资格要求的 canonical observations。"
    elif eligible_count == 1:
        state = READINESS_SINGLE_SNAPSHOT
        label = "单个 qualified observation"
        reason = "当前只有一个 qualified observation，可用于事实检查，不足以描述多日历史。"
    elif date_count <= 1:
        state = READINESS_SINGLE_DATE
        label = "单日 qualified 历史"
        reason = "qualified observations 只覆盖一个交易日。"
    elif date_count < int(min_qualified_dates or 3):
        state = READINESS_LIMITED_MULTI_DAY
        label = "有限 qualified 多日历史"
        reason = f"qualified observations 覆盖 {date_count} 个交易日，低于 {int(min_qualified_dates or 3)} 日多日观察门槛。"
    else:
        state = READINESS_READY
        label = "contract-qualified 多日历史可用"
        reason = f"qualified observations 覆盖 {date_count} 个交易日，可用于该 workload 的多日历史观察。"
    return {
        "qualified_readiness_state": state,
        "qualified_readiness_label": label,
        "qualified_readiness_reason": reason,
        "min_qualified_dates": int(min_qualified_dates or 3),
    }


def build_qualified_universe_summary(
    df: pd.DataFrame | None,
    workload: str | None = WORKLOAD_THEME_CONTINUITY,
    min_qualified_dates: int = 3,
) -> dict:
    workload_name = normalize_analytical_workload(workload)
    if df is None or df.empty:
        summary = {
            "workload": workload_name,
            "input_observation_count": 0,
            "eligible_observation_count": 0,
            "excluded_observation_count": 0,
            "eligible_trade_date_count": 0,
            "eligible_trade_dates": [],
            "eligible_captured_time_bucket_count": 0,
            "eligible_continuity_segment_count": 0,
            "eligible_continuity_segments": [],
            "excluded_reason_counts": {},
            "eligibility_state_counts": {},
            "provider_contract_resolution_counts": {},
            "source_mode_counts": {},
            "eligible_observations_by_date": {},
            "eligible_trade_dates_by_continuity_segment": {},
        }
        summary.update(classify_qualified_analytical_readiness(summary, min_qualified_dates=min_qualified_dates))
        return summary

    work = attach_analytical_eligibility(df, workload=workload_name)
    eligible = work[work["is_analytically_eligible"].fillna(False).astype(bool)].copy()
    excluded = work[~work["is_analytically_eligible"].fillna(False).astype(bool)].copy()
    eligible_dates = sorted(eligible["trade_date"].dropna().astype(str).unique().tolist()) if "trade_date" in eligible.columns else []
    eligible_segments = sorted(eligible[CONTINUITY_SEGMENT_COLUMN].dropna().astype(str).unique().tolist()) if CONTINUITY_SEGMENT_COLUMN in eligible.columns else []
    by_date = eligible.groupby(eligible["trade_date"].astype(str)).size().astype(int).to_dict() if "trade_date" in eligible.columns and not eligible.empty else {}
    if CONTINUITY_SEGMENT_COLUMN in eligible.columns and "trade_date" in eligible.columns and not eligible.empty:
        segment_dates = eligible.groupby(CONTINUITY_SEGMENT_COLUMN)["trade_date"].nunique().astype(int).to_dict()
    else:
        segment_dates = {}
    summary = {
        "workload": workload_name,
        "input_observation_count": int(len(work)),
        "eligible_observation_count": int(len(eligible)),
        "excluded_observation_count": int(len(excluded)),
        "eligible_trade_date_count": int(len(eligible_dates)),
        "eligible_trade_dates": eligible_dates,
        "eligible_captured_time_bucket_count": int(eligible["captured_time_bucket"].dropna().astype(str).nunique()) if "captured_time_bucket" in eligible.columns and not eligible.empty else 0,
        "eligible_continuity_segment_count": int(len(eligible_segments)),
        "eligible_continuity_segments": eligible_segments,
        "excluded_reason_counts": _value_counts(excluded, "analytical_eligibility_reason"),
        "eligibility_state_counts": _value_counts(work, "analytical_eligibility_state"),
        "provider_contract_resolution_counts": _value_counts(work, "provider_contract_resolution_state"),
        "source_mode_counts": _value_counts(work, "source_mode"),
        "eligible_observations_by_date": {str(k): int(v) for k, v in by_date.items()},
        "eligible_trade_dates_by_continuity_segment": {str(k): int(v) for k, v in segment_dates.items()},
    }
    summary.update(classify_qualified_analytical_readiness(summary, min_qualified_dates=min_qualified_dates))
    return summary


def build_availability_vs_qualified_readiness(
    availability_readiness: dict | None,
    observations_df: pd.DataFrame | None,
    workload: str | None = WORKLOAD_THEME_CONTINUITY,
    min_qualified_dates: int = 3,
) -> dict:
    qualified = build_qualified_universe_summary(
        observations_df,
        workload=workload,
        min_qualified_dates=min_qualified_dates,
    )
    availability = dict(availability_readiness or {})
    return {
        "availability_readiness_state": availability.get("readiness_state"),
        "availability_readiness_label": availability.get("readiness_label"),
        "availability_readiness_reason": availability.get("readiness_reason"),
        "qualified_readiness_state": qualified.get("qualified_readiness_state"),
        "qualified_readiness_label": qualified.get("qualified_readiness_label"),
        "qualified_readiness_reason": qualified.get("qualified_readiness_reason"),
        "qualified_summary": qualified,
        "readiness_separation_semantics": "historical availability readiness does not imply workload-specific qualified analytical readiness.",
    }


def summarize_analytical_eligibility(summary: dict) -> str:
    workload = summary.get("workload") or "--"
    eligible = int(summary.get("eligible_observation_count", 0) or 0)
    excluded = int(summary.get("excluded_observation_count", 0) or 0)
    dates = int(summary.get("eligible_trade_date_count", 0) or 0)
    label = summary.get("qualified_readiness_label") or "--"
    return (
        f"{workload} 的 qualified universe 包含 {eligible} 条 observations、{dates} 个交易日；"
        f"排除 {excluded} 条未满足该 workload 资格要求的 observations。当前状态：{label}。"
    )


def validate_analytical_eligibility_text(text: str) -> list[str]:
    value = str(text or "")
    return [word for word in FORBIDDEN_ANALYTICAL_ELIGIBILITY_WORDS if word in value]
