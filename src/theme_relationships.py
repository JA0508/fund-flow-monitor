from __future__ import annotations

import hashlib
import json
from collections import Counter
from itertools import combinations
from typing import Iterable

import pandas as pd

from src.analytical_continuity import CONTINUITY_SEGMENT_COLUMN, attach_continuity_columns
from src.theme_dynamics import (
    CANONICAL_BUCKET_POLICY,
    DYNAMICS_DEFAULT_BASIS,
    build_theme_observation_cube,
    normalize_theme_dynamics_mode,
)
from src.theme_regimes import attach_regime_signatures_to_observations
from src.theme_taxonomy import build_taxonomy_fingerprint, load_theme_taxonomy
from src.theme_taxonomy_audit import build_cross_theme_overlap_audit

PAIR_GRAIN = (
    "theme_pair",
    "trade_date",
    "captured_time_bucket",
    "calculation_mode",
    "source_mode",
    CONTINUITY_SEGMENT_COLUMN,
    "taxonomy_fingerprint",
)

RELATIONSHIP_FORBIDDEN_WORDS = (
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
    "概率",
    "胜率",
    "因果",
    "领先",
    "滞后",
    "lead-lag",
    "predictive",
    "causal",
    "probability",
)

STATE_SIGN_GROUPS = {
    "强流入": "positive",
    "弱流入": "positive",
    "分歧/中性": "neutral",
    "弱流出": "negative",
    "强流出": "negative",
}

ALIGNMENT_DENOMINATOR = "all aligned canonical pair observations for the selected pair/mode/source/taxonomy lineage"
TRANSITION_DENOMINATOR = "aligned consecutive transition steps where at least one theme changed the measured dimension"
MIN_DISPLAY_ALIGNED_OBSERVATIONS = 3
MIN_DISPLAY_REPRESENTED_TRADE_DATES = 2


def _stable_id(payload: object, length: int = 20) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _share(numerator: int | float, denominator: int | float) -> float:
    try:
        denom = float(denominator)
        if denom == 0:
            return 0.0
        return round(float(numerator) / denom, 4)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def normalize_theme_pair(theme_a: str, theme_b: str) -> tuple[str, str]:
    left = str(theme_a or "").strip()
    right = str(theme_b or "").strip()
    ordered = tuple(sorted((left, right)))
    return ordered[0], ordered[1]


def build_theme_pair_id(theme_a: str, theme_b: str, taxonomy_fingerprint: str | None = None) -> str:
    left, right = normalize_theme_pair(theme_a, theme_b)
    return _stable_id({"theme_a": left, "theme_b": right, "taxonomy_fingerprint": taxonomy_fingerprint or ""})


def get_theme_relationship_pair_grain() -> tuple[str, ...]:
    return PAIR_GRAIN


def get_relationship_observation_basis() -> str:
    return DYNAMICS_DEFAULT_BASIS


def _state_sign(state: object) -> str:
    return STATE_SIGN_GROUPS.get(str(state or "分歧/中性"), "neutral")


def _direction_code(state: object) -> int:
    sign = _state_sign(state)
    if sign == "positive":
        return 1
    if sign == "negative":
        return -1
    return 0


def _listify(value: object) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [value]


def _prepare_regime_observations(cube_df: pd.DataFrame, calculation_mode: str) -> pd.DataFrame:
    mode = normalize_theme_dynamics_mode(calculation_mode)
    regime = attach_regime_signatures_to_observations(cube_df, calculation_mode=mode)
    if regime is None or regime.empty:
        return pd.DataFrame()
    regime = regime.copy()
    required = {
        "headline_state": regime.get("headline_state", regime.get("derived_state")),
        "headline_state_code": regime.get("headline_state_code", regime.get("state_code")),
        "scope_divergence_state": regime.get("scope_divergence_state", pd.Series(["insufficient_scopes"] * len(regime))),
        "member_divergence_state": regime.get("member_divergence_state", pd.Series(["unknown"] * len(regime))),
    }
    for column, values in required.items():
        if column not in regime.columns:
            regime[column] = values
    regime["calculation_mode"] = regime["calculation_mode"].astype(str)
    regime["source_mode"] = regime["source_mode"].astype(str).str.upper()
    return regime


def _empty_pairs(warnings: list[str] | None = None) -> pd.DataFrame:
    df = pd.DataFrame()
    df.attrs["pair_grain"] = PAIR_GRAIN
    df.attrs["relationship_observation_basis"] = DYNAMICS_DEFAULT_BASIS
    df.attrs["materialization_policy"] = CANONICAL_BUCKET_POLICY
    df.attrs["warnings"] = warnings or []
    return df


def build_aligned_theme_pairs(
    cube_df: pd.DataFrame,
    calculation_mode: str = "strict_representative",
    source_mode: str | None = None,
    taxonomy: dict | None = None,
    themes: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Build exact aligned theme-pair facts from canonical bucket observations."""

    if cube_df is None or cube_df.empty:
        return _empty_pairs(["暂无 canonical observations 可用于主题关系对齐。"])

    mode = normalize_theme_dynamics_mode(calculation_mode)
    regime = _prepare_regime_observations(cube_df, mode)
    if regime.empty:
        return _empty_pairs([f"暂无 {mode} 口径 canonical observations。"])
    regime = attach_continuity_columns(regime)

    source = str(source_mode or "").upper().strip()
    if source:
        regime = regime[regime["source_mode"].astype(str).str.upper().eq(source)].copy()
    if themes:
        allowed = {str(item) for item in themes}
        regime = regime[regime["theme_name"].astype(str).isin(allowed)].copy()
    if regime.empty:
        return _empty_pairs(["筛选后暂无可对齐 canonical observations。"])

    taxonomy = taxonomy or load_theme_taxonomy()
    expected_taxonomy_fp = build_taxonomy_fingerprint(taxonomy) if taxonomy else None
    observed_taxonomy = sorted(regime["taxonomy_fingerprint"].dropna().astype(str).unique().tolist())
    warnings: list[str] = list(getattr(cube_df, "attrs", {}).get("warnings", []))
    if len(observed_taxonomy) > 1:
        warnings.append("检测到多个 taxonomy_fingerprint；主题关系证据按 lineage 分组，不静默混合。")
    if expected_taxonomy_fp and observed_taxonomy and expected_taxonomy_fp not in observed_taxonomy:
        warnings.append("当前 taxonomy fingerprint 与 canonical observations 中的 lineage 不完全一致。")

    key_cols = [
        "trade_date",
        "captured_time_bucket",
        "calculation_mode",
        "source_mode",
        CONTINUITY_SEGMENT_COLUMN,
        "taxonomy_fingerprint",
    ]
    themes_all = sorted(regime["theme_name"].dropna().astype(str).unique().tolist())
    candidate_pairs = [normalize_theme_pair(left, right) for left, right in combinations(themes_all, 2)]
    rows: list[dict] = []

    grouped = regime.sort_values(key_cols + ["theme_name"], na_position="last").groupby(key_cols, dropna=False, sort=True)
    for key, group in grouped:
        values = dict(zip(key_cols, key if isinstance(key, tuple) else (key,)))
        by_theme = {str(row.get("theme_name")): row for _, row in group.iterrows()}
        for left, right in candidate_pairs:
            left_row = by_theme.get(left)
            right_row = by_theme.get(right)
            pair_id = build_theme_pair_id(left, right, values.get("taxonomy_fingerprint"))
            if left_row is None or right_row is None:
                rows.append(
                    {
                        **values,
                        "theme_a": left,
                        "theme_b": right,
                        "theme_pair": f"{left}::{right}",
                        "pair_id": pair_id,
                        "alignment_status": "missing_theme_a" if left_row is None else "missing_theme_b",
                        "is_aligned": False,
                    }
                )
                continue
            rows.append(
                {
                    **values,
                    "theme_a": left,
                    "theme_b": right,
                    "theme_pair": f"{left}::{right}",
                    "pair_id": pair_id,
                    "theme_a_definition_fingerprint": left_row.get("theme_definition_fingerprint"),
                    "theme_b_definition_fingerprint": right_row.get("theme_definition_fingerprint"),
                    "theme_a_canonical_observation_id": left_row.get("canonical_observation_id"),
                    "theme_b_canonical_observation_id": right_row.get("canonical_observation_id"),
                    "theme_a_selected_snapshot_id": left_row.get("selected_snapshot_id"),
                    "theme_b_selected_snapshot_id": right_row.get("selected_snapshot_id"),
                    "theme_a_selected_event_observation_id": left_row.get("selected_event_observation_id"),
                    "theme_b_selected_event_observation_id": right_row.get("selected_event_observation_id"),
                    "theme_a_provider_contract_id": left_row.get("provider_contract_id"),
                    "theme_b_provider_contract_id": right_row.get("provider_contract_id"),
                    "theme_a_provider_contract_resolution_state": left_row.get("provider_contract_resolution_state"),
                    "theme_b_provider_contract_resolution_state": right_row.get("provider_contract_resolution_state"),
                    "theme_a_headline_state": left_row.get("headline_state") or left_row.get("derived_state"),
                    "theme_b_headline_state": right_row.get("headline_state") or right_row.get("derived_state"),
                    "theme_a_headline_state_code": left_row.get("headline_state_code") if pd.notna(left_row.get("headline_state_code")) else left_row.get("state_code"),
                    "theme_b_headline_state_code": right_row.get("headline_state_code") if pd.notna(right_row.get("headline_state_code")) else right_row.get("state_code"),
                    "theme_a_regime_signature": left_row.get("regime_signature"),
                    "theme_b_regime_signature": right_row.get("regime_signature"),
                    "theme_a_scope_divergence_state": left_row.get("scope_divergence_state"),
                    "theme_b_scope_divergence_state": right_row.get("scope_divergence_state"),
                    "theme_a_member_divergence_state": left_row.get("member_divergence_state"),
                    "theme_b_member_divergence_state": right_row.get("member_divergence_state"),
                    "alignment_status": "aligned",
                    "is_aligned": True,
                }
            )

    result = pd.DataFrame(rows)
    if result.empty:
        return _empty_pairs(warnings)
    result = result.sort_values(
        ["theme_a", "theme_b", "source_mode", CONTINUITY_SEGMENT_COLUMN, "taxonomy_fingerprint", "trade_date", "captured_time_bucket"],
        na_position="last",
    ).reset_index(drop=True)
    result.attrs["pair_grain"] = PAIR_GRAIN
    result.attrs["candidate_pair_count"] = len(candidate_pairs)
    result.attrs["relationship_observation_basis"] = DYNAMICS_DEFAULT_BASIS
    result.attrs["materialization_policy"] = CANONICAL_BUCKET_POLICY
    result.attrs["warnings"] = warnings
    return result


def build_pair_alignment_summary(pair_df: pd.DataFrame) -> dict:
    if pair_df is None or pair_df.empty:
        return {
            "candidate_pair_count": 0,
            "aligned_pair_observation_count": 0,
            "alignment_count_by_pair": {},
            "missing_alignment_count_by_pair": {},
            "represented_trade_dates_by_pair": {},
            "represented_buckets_by_pair": {},
        }
    aligned = pair_df[pair_df["is_aligned"].astype(bool)].copy() if "is_aligned" in pair_df.columns else pd.DataFrame()
    missing = pair_df[~pair_df["is_aligned"].astype(bool)].copy() if "is_aligned" in pair_df.columns else pd.DataFrame()
    return {
        "candidate_pair_count": int(pair_df["pair_id"].nunique()) if "pair_id" in pair_df.columns else 0,
        "aligned_pair_observation_count": int(len(aligned)),
        "alignment_count_by_pair": aligned.groupby("theme_pair").size().astype(int).to_dict() if not aligned.empty else {},
        "missing_alignment_count_by_pair": missing.groupby("theme_pair").size().astype(int).to_dict() if not missing.empty else {},
        "represented_trade_dates_by_pair": aligned.groupby("theme_pair")["trade_date"].nunique().astype(int).to_dict() if not aligned.empty else {},
        "represented_buckets_by_pair": aligned.groupby("theme_pair")["captured_time_bucket"].nunique().astype(int).to_dict() if not aligned.empty else {},
    }


def filter_pair_observations(pair_df: pd.DataFrame, theme_a: str | None = None, theme_b: str | None = None) -> pd.DataFrame:
    if pair_df is None or pair_df.empty:
        return pd.DataFrame()
    if not theme_a and not theme_b:
        return pair_df.copy()
    if theme_a and theme_b:
        left, right = normalize_theme_pair(theme_a, theme_b)
        return pair_df[pair_df["theme_a"].astype(str).eq(left) & pair_df["theme_b"].astype(str).eq(right)].copy()
    theme = str(theme_a or theme_b)
    return pair_df[pair_df["theme_a"].astype(str).eq(theme) | pair_df["theme_b"].astype(str).eq(theme)].copy()


def build_headline_state_agreement(pair_observations: pd.DataFrame) -> dict:
    aligned = pair_observations[pair_observations["is_aligned"].astype(bool)].copy() if pair_observations is not None and not pair_observations.empty else pd.DataFrame()
    denominator = int(len(aligned))
    if denominator == 0:
        return {
            "aligned_observation_count": 0,
            "exact_headline_state_agreement_count": 0,
            "exact_headline_state_agreement_share": 0.0,
            "same_sign_count": 0,
            "same_sign_share": 0.0,
            "opposing_sign_count": 0,
            "opposing_sign_share": 0.0,
            "both_positive_count": 0,
            "both_neutral_count": 0,
            "both_negative_count": 0,
            "one_neutral_count": 0,
            "state_pair_counts": {},
            "joint_state_table": [],
            "denominator_note": ALIGNMENT_DENOMINATOR,
        }
    a_state = aligned["theme_a_headline_state"].astype(str)
    b_state = aligned["theme_b_headline_state"].astype(str)
    a_sign = a_state.map(_state_sign)
    b_sign = b_state.map(_state_sign)
    exact = a_state.eq(b_state)
    same_sign = a_sign.eq(b_sign)
    opposing = ((a_sign.eq("positive") & b_sign.eq("negative")) | (a_sign.eq("negative") & b_sign.eq("positive")))
    pair_counts = Counter(f"{left} × {right}" for left, right in zip(a_state, b_state))
    joint = (
        aligned.assign(theme_a_state=a_state, theme_b_state=b_state)
        .groupby(["theme_a_state", "theme_b_state"], dropna=False)
        .size()
        .reset_index(name="aligned_observation_count")
        .to_dict(orient="records")
    )
    return {
        "aligned_observation_count": denominator,
        "exact_headline_state_agreement_count": int(exact.sum()),
        "exact_headline_state_agreement_share": _share(int(exact.sum()), denominator),
        "same_sign_count": int(same_sign.sum()),
        "same_sign_share": _share(int(same_sign.sum()), denominator),
        "opposing_sign_count": int(opposing.sum()),
        "opposing_sign_share": _share(int(opposing.sum()), denominator),
        "both_positive_count": int((a_sign.eq("positive") & b_sign.eq("positive")).sum()),
        "both_neutral_count": int((a_sign.eq("neutral") & b_sign.eq("neutral")).sum()),
        "both_negative_count": int((a_sign.eq("negative") & b_sign.eq("negative")).sum()),
        "one_neutral_count": int(((a_sign.eq("neutral") & ~b_sign.eq("neutral")) | (~a_sign.eq("neutral") & b_sign.eq("neutral"))).sum()),
        "state_pair_counts": dict(pair_counts),
        "joint_state_table": joint,
        "denominator_note": ALIGNMENT_DENOMINATOR,
    }


def build_structural_regime_alignment(pair_observations: pd.DataFrame) -> dict:
    aligned = pair_observations[pair_observations["is_aligned"].astype(bool)].copy() if pair_observations is not None and not pair_observations.empty else pd.DataFrame()
    denominator = int(len(aligned))
    if denominator == 0:
        return {
            "same_regime_signature_count": 0,
            "same_regime_signature_share": 0.0,
            "headline_aligned_regime_different_count": 0,
            "headline_aligned_regime_different_share": 0.0,
            "same_scope_structure_count": 0,
            "same_scope_structure_share": 0.0,
            "same_member_structure_count": 0,
            "same_member_structure_share": 0.0,
            "structurally_different_count": 0,
            "recent_headline_aligned_regime_different_examples": [],
            "denominator_note": ALIGNMENT_DENOMINATOR,
        }
    same_regime = aligned["theme_a_regime_signature"].astype(str).eq(aligned["theme_b_regime_signature"].astype(str))
    same_headline = aligned["theme_a_headline_state"].astype(str).eq(aligned["theme_b_headline_state"].astype(str))
    regime_diff_same_headline = same_headline & ~same_regime
    same_scope = aligned["theme_a_scope_divergence_state"].astype(str).eq(aligned["theme_b_scope_divergence_state"].astype(str))
    same_member = aligned["theme_a_member_divergence_state"].astype(str).eq(aligned["theme_b_member_divergence_state"].astype(str))
    examples = (
        aligned[regime_diff_same_headline]
        .sort_values(["trade_date", "captured_time_bucket"], ascending=False)
        .head(5)[
            [
                "trade_date",
                "captured_time_bucket",
                "theme_a_headline_state",
                "theme_a_regime_signature",
                "theme_b_regime_signature",
                "theme_a_scope_divergence_state",
                "theme_b_scope_divergence_state",
                "theme_a_member_divergence_state",
                "theme_b_member_divergence_state",
            ]
        ]
        .to_dict(orient="records")
        if regime_diff_same_headline.any()
        else []
    )
    return {
        "same_regime_signature_count": int(same_regime.sum()),
        "same_regime_signature_share": _share(int(same_regime.sum()), denominator),
        "headline_aligned_regime_different_count": int(regime_diff_same_headline.sum()),
        "headline_aligned_regime_different_share": _share(int(regime_diff_same_headline.sum()), int(same_headline.sum())),
        "headline_aligned_denominator": int(same_headline.sum()),
        "same_scope_structure_count": int(same_scope.sum()),
        "same_scope_structure_share": _share(int(same_scope.sum()), denominator),
        "same_member_structure_count": int(same_member.sum()),
        "same_member_structure_share": _share(int(same_member.sum()), denominator),
        "structurally_different_count": int((~same_regime).sum()),
        "recent_headline_aligned_regime_different_examples": examples,
        "denominator_note": ALIGNMENT_DENOMINATOR,
        "headline_aligned_regime_different_denominator_note": "headline-aligned canonical pair observations for the selected pair/mode/source/taxonomy lineage",
    }


def _state_direction_delta(previous: object, current: object) -> int:
    return _direction_code(current) - _direction_code(previous)


def build_observed_co_transition_evidence(pair_observations: pd.DataFrame) -> dict:
    aligned = pair_observations[pair_observations["is_aligned"].astype(bool)].copy() if pair_observations is not None and not pair_observations.empty else pd.DataFrame()
    if aligned.empty:
        return {
            "aligned_transition_step_count": 0,
            "theme_a_headline_change_count": 0,
            "theme_b_headline_change_count": 0,
            "simultaneous_headline_change_count": 0,
            "simultaneous_headline_change_share": 0.0,
            "theme_a_structural_change_count": 0,
            "theme_b_structural_change_count": 0,
            "simultaneous_structural_change_count": 0,
            "simultaneous_structural_change_share": 0.0,
            "simultaneous_headline_preserving_structural_change_count": 0,
            "opposite_direction_state_change_count": 0,
            "headline_change_denominator": 0,
            "structural_change_denominator": 0,
            "denominator_note": TRANSITION_DENOMINATOR,
        }
    lineage_cols = [
        "source_mode",
        "taxonomy_fingerprint",
        "theme_a_definition_fingerprint",
        "theme_b_definition_fingerprint",
        "calculation_mode",
    ]
    for col in lineage_cols:
        if col not in aligned.columns:
            aligned[col] = None
    ordered = aligned.sort_values(["source_mode", "taxonomy_fingerprint", "theme_a_definition_fingerprint", "theme_b_definition_fingerprint", "trade_date", "captured_time_bucket"], na_position="last")
    transition_steps = 0
    a_headline = b_headline = both_headline = 0
    a_struct = b_struct = both_struct = 0
    headline_preserving_both_struct = 0
    opposite_direction = 0
    headline_denominator = 0
    structural_denominator = 0
    group_cols = ["source_mode", "taxonomy_fingerprint", "theme_a_definition_fingerprint", "theme_b_definition_fingerprint", "calculation_mode"]
    for _, group in ordered.groupby(group_cols, dropna=False, sort=True):
        rows = group.reset_index(drop=True)
        for idx in range(1, len(rows)):
            previous = rows.iloc[idx - 1]
            current = rows.iloc[idx]
            transition_steps += 1
            a_h = str(previous.get("theme_a_headline_state")) != str(current.get("theme_a_headline_state"))
            b_h = str(previous.get("theme_b_headline_state")) != str(current.get("theme_b_headline_state"))
            a_s = str(previous.get("theme_a_regime_signature")) != str(current.get("theme_a_regime_signature"))
            b_s = str(previous.get("theme_b_regime_signature")) != str(current.get("theme_b_regime_signature"))
            if a_h:
                a_headline += 1
            if b_h:
                b_headline += 1
            if a_h or b_h:
                headline_denominator += 1
            if a_h and b_h:
                both_headline += 1
                a_delta = _state_direction_delta(previous.get("theme_a_headline_state"), current.get("theme_a_headline_state"))
                b_delta = _state_direction_delta(previous.get("theme_b_headline_state"), current.get("theme_b_headline_state"))
                if a_delta and b_delta and (a_delta * b_delta < 0):
                    opposite_direction += 1
            if a_s:
                a_struct += 1
            if b_s:
                b_struct += 1
            if a_s or b_s:
                structural_denominator += 1
            if a_s and b_s:
                both_struct += 1
                if not a_h and not b_h:
                    headline_preserving_both_struct += 1
    return {
        "aligned_transition_step_count": int(transition_steps),
        "theme_a_headline_change_count": int(a_headline),
        "theme_b_headline_change_count": int(b_headline),
        "simultaneous_headline_change_count": int(both_headline),
        "simultaneous_headline_change_share": _share(both_headline, headline_denominator),
        "theme_a_structural_change_count": int(a_struct),
        "theme_b_structural_change_count": int(b_struct),
        "simultaneous_structural_change_count": int(both_struct),
        "simultaneous_structural_change_share": _share(both_struct, structural_denominator),
        "simultaneous_headline_preserving_structural_change_count": int(headline_preserving_both_struct),
        "opposite_direction_state_change_count": int(opposite_direction),
        "headline_change_denominator": int(headline_denominator),
        "structural_change_denominator": int(structural_denominator),
        "denominator_note": TRANSITION_DENOMINATOR,
    }


def build_pair_semantic_overlap_lookup(taxonomy: dict | None = None) -> dict[str, dict]:
    overlap_df = build_cross_theme_overlap_audit(taxonomy)
    lookup: dict[str, dict] = {}
    if overlap_df.empty:
        return lookup
    taxonomy_fp = build_taxonomy_fingerprint(taxonomy or load_theme_taxonomy())
    for _, row in overlap_df.iterrows():
        left, right = normalize_theme_pair(row.get("theme_left"), row.get("theme_right"))
        pair_id = build_theme_pair_id(left, right, taxonomy_fp)
        record = row.to_dict()
        record.update({"theme_a": left, "theme_b": right, "pair_id": pair_id, "taxonomy_fingerprint": taxonomy_fp})
        lookup[f"{left}::{right}"] = record
    return lookup


def get_pair_semantic_overlap(theme_a: str, theme_b: str, taxonomy: dict | None = None) -> dict:
    left, right = normalize_theme_pair(theme_a, theme_b)
    lookup = build_pair_semantic_overlap_lookup(taxonomy)
    return lookup.get(
        f"{left}::{right}",
        {
            "theme_a": left,
            "theme_b": right,
            "shared_members": [],
            "shared_member_count": 0,
            "member_union_count": 0,
            "jaccard_overlap": 0.0,
            "shared_strict_representatives": [],
            "shared_strict_count": 0,
            "overlap_state": "none",
        },
    )


def build_theme_relationship_evidence(
    pair_df: pd.DataFrame,
    theme_a: str,
    theme_b: str,
    taxonomy: dict | None = None,
) -> dict:
    left, right = normalize_theme_pair(theme_a, theme_b)
    pair_obs_all = filter_pair_observations(pair_df, left, right)
    if pair_obs_all.empty:
        return {
            "relationship_available": False,
            "theme_a": left,
            "theme_b": right,
            "pair_id": build_theme_pair_id(left, right),
            "warnings": ["未找到该主题对的 canonical alignment evidence。"],
            "errors": [],
        }
    aligned = pair_obs_all[pair_obs_all["is_aligned"].astype(bool)].copy()
    taxonomy_fp = str(pair_obs_all["taxonomy_fingerprint"].dropna().astype(str).iloc[0]) if "taxonomy_fingerprint" in pair_obs_all.columns and pair_obs_all["taxonomy_fingerprint"].dropna().size else None
    semantic = get_pair_semantic_overlap(left, right, taxonomy)
    headline = build_headline_state_agreement(pair_obs_all)
    structural = build_structural_regime_alignment(pair_obs_all)
    transitions = build_observed_co_transition_evidence(pair_obs_all)
    warnings = list(getattr(pair_df, "attrs", {}).get("warnings", []))
    if aligned.empty:
        warnings.append("该主题对暂无 aligned canonical observations；缺口仍保留在 alignment evidence 中。")
    if sorted(pair_obs_all["source_mode"].dropna().astype(str).str.upper().unique().tolist()) and len(pair_obs_all["source_mode"].dropna().astype(str).str.upper().unique()) > 1:
        warnings.append("该主题对包含多个 source_mode；关系证据不应静默混合解释。")
    return {
        "relationship_available": bool(not aligned.empty),
        "pair_id": build_theme_pair_id(left, right, taxonomy_fp),
        "theme_a": left,
        "theme_b": right,
        "theme_pair": f"{left}::{right}",
        "calculation_mode": str(pair_obs_all["calculation_mode"].dropna().astype(str).iloc[0]) if "calculation_mode" in pair_obs_all.columns and pair_obs_all["calculation_mode"].dropna().size else None,
        "source_mode": str(pair_obs_all["source_mode"].dropna().astype(str).iloc[0]) if "source_mode" in pair_obs_all.columns and pair_obs_all["source_mode"].dropna().size else None,
        "taxonomy_fingerprint": taxonomy_fp,
        "theme_a_definition_fingerprint": str(pair_obs_all["theme_a_definition_fingerprint"].dropna().astype(str).iloc[0]) if "theme_a_definition_fingerprint" in pair_obs_all.columns and pair_obs_all["theme_a_definition_fingerprint"].dropna().size else None,
        "theme_b_definition_fingerprint": str(pair_obs_all["theme_b_definition_fingerprint"].dropna().astype(str).iloc[0]) if "theme_b_definition_fingerprint" in pair_obs_all.columns and pair_obs_all["theme_b_definition_fingerprint"].dropna().size else None,
        "aligned_observation_count": int(len(aligned)),
        "alignment_gap_count": int((~pair_obs_all["is_aligned"].astype(bool)).sum()),
        "represented_trade_date_count": int(aligned["trade_date"].nunique()) if not aligned.empty else 0,
        "represented_captured_time_bucket_count": int(aligned["captured_time_bucket"].nunique()) if not aligned.empty else 0,
        "semantic_overlap": semantic,
        "headline_state_evidence": headline,
        "structural_regime_evidence": structural,
        "co_transition_evidence": transitions,
        "canonical_materialization_basis": DYNAMICS_DEFAULT_BASIS,
        "materialization_policy": CANONICAL_BUCKET_POLICY,
        "warnings": warnings,
        "errors": [],
    }


def build_relationship_topology_summary(
    pair_df: pd.DataFrame,
    taxonomy: dict | None = None,
    sort_by: str = "jaccard_overlap",
    min_aligned_observations: int = MIN_DISPLAY_ALIGNED_OBSERVATIONS,
    min_represented_trade_dates: int = MIN_DISPLAY_REPRESENTED_TRADE_DATES,
) -> pd.DataFrame:
    if pair_df is None or pair_df.empty:
        return pd.DataFrame()
    rows: list[dict] = []
    pairs = pair_df[["theme_a", "theme_b"]].drop_duplicates().sort_values(["theme_a", "theme_b"])
    for _, row in pairs.iterrows():
        evidence = build_theme_relationship_evidence(pair_df, row.get("theme_a"), row.get("theme_b"), taxonomy=taxonomy)
        semantic = evidence.get("semantic_overlap", {})
        headline = evidence.get("headline_state_evidence", {})
        structural = evidence.get("structural_regime_evidence", {})
        transitions = evidence.get("co_transition_evidence", {})
        aligned_observations = int(evidence.get("aligned_observation_count", 0) or 0)
        represented_trade_dates = int(evidence.get("represented_trade_date_count", 0) or 0)
        exclusion_reasons = []
        if aligned_observations < int(min_aligned_observations):
            exclusion_reasons.append("below_min_aligned_observations")
        if represented_trade_dates < int(min_represented_trade_dates):
            exclusion_reasons.append("below_min_represented_trade_dates")
        rows.append(
            {
                "theme_pair": evidence.get("theme_pair"),
                "theme_a": evidence.get("theme_a"),
                "theme_b": evidence.get("theme_b"),
                "aligned_observations": aligned_observations,
                "alignment_gaps": evidence.get("alignment_gap_count", 0),
                "represented_trade_dates": represented_trade_dates,
                "taxonomy_jaccard": semantic.get("jaccard_overlap", 0.0),
                "shared_member_count": semantic.get("shared_member_count", 0),
                "same_sign_count": headline.get("same_sign_count", 0),
                "same_sign_observed_share": headline.get("same_sign_share", 0.0),
                "exact_state_agreement_count": headline.get("exact_headline_state_agreement_count", 0),
                "exact_state_observed_share": headline.get("exact_headline_state_agreement_share", 0.0),
                "same_regime_count": structural.get("same_regime_signature_count", 0),
                "same_regime_observed_share": structural.get("same_regime_signature_share", 0.0),
                "headline_aligned_regime_different_count": structural.get("headline_aligned_regime_different_count", 0),
                "headline_aligned_regime_different_share": structural.get("headline_aligned_regime_different_share", 0.0),
                "simultaneous_headline_change_count": transitions.get("simultaneous_headline_change_count", 0),
                "simultaneous_structural_change_count": transitions.get("simultaneous_structural_change_count", 0),
                "display_min_aligned_observations": int(min_aligned_observations),
                "display_min_represented_trade_dates": int(min_represented_trade_dates),
                "display_eligible": not exclusion_reasons,
                "exclusion_reasons": ", ".join(exclusion_reasons),
                "denominator_context": (
                    f"{headline.get('same_sign_count', 0)}/{aligned_observations} aligned observations, "
                    f"{represented_trade_dates} trade dates"
                ),
                "warnings": "; ".join(evidence.get("warnings", [])[:2]),
            }
        )
    result = pd.DataFrame(rows)
    sort_map = {
        "jaccard_overlap": "taxonomy_jaccard",
        "same_sign_observed_share": "same_sign_observed_share",
        "structural_contrast_count": "headline_aligned_regime_different_count",
        "exact_state_observed_share": "exact_state_observed_share",
    }
    column = sort_map.get(sort_by, sort_by)
    if column in result.columns:
        result = result.sort_values([column, "aligned_observations", "theme_pair"], ascending=[False, False, True]).reset_index(drop=True)
    result.attrs["display_sufficiency"] = {
        "minimum_aligned_observations": int(min_aligned_observations),
        "minimum_represented_trade_dates": int(min_represented_trade_dates),
        "total_candidate_pairs": int(len(result)),
        "pairs_meeting_display_sufficiency": int(result["display_eligible"].sum()) if "display_eligible" in result.columns else int(len(result)),
        "excluded_pair_count": int((~result["display_eligible"].astype(bool)).sum()) if "display_eligible" in result.columns else 0,
        "exclusion_reasons": result["exclusion_reasons"].value_counts().astype(int).to_dict() if "exclusion_reasons" in result.columns else {},
    }
    return result


def build_theme_relationships_from_cube(
    cube_df: pd.DataFrame,
    calculation_mode: str = "strict_representative",
    source_mode: str | None = None,
    taxonomy: dict | None = None,
    themes: Iterable[str] | None = None,
) -> dict:
    pair_df = build_aligned_theme_pairs(cube_df, calculation_mode=calculation_mode, source_mode=source_mode, taxonomy=taxonomy, themes=themes)
    return {
        "pair_observations": pair_df,
        "alignment_summary": build_pair_alignment_summary(pair_df),
        "topology_summary": build_relationship_topology_summary(pair_df, taxonomy=taxonomy),
        "warnings": list(getattr(pair_df, "attrs", {}).get("warnings", [])),
        "relationship_observation_basis": DYNAMICS_DEFAULT_BASIS,
        "materialization_policy": CANONICAL_BUCKET_POLICY,
    }


def build_theme_relationships_from_source(
    source_mode: str = "SAMPLE",
    calculation_mode: str = "strict_representative",
    taxonomy: dict | None = None,
    data_dir: str | None = None,
    limit_dates: int | None = None,
) -> dict:
    taxonomy = taxonomy or load_theme_taxonomy()
    cube = build_theme_observation_cube(
        taxonomy=taxonomy,
        source_mode=source_mode,
        data_dir=data_dir,
        limit_dates=limit_dates,
    )
    return build_theme_relationships_from_cube(
        cube,
        calculation_mode=calculation_mode,
        source_mode=source_mode,
        taxonomy=taxonomy,
    )


def render_theme_relationship_brief_section(evidence: dict, heading_level: int = 2) -> str:
    prefix = "#" * max(2, min(int(heading_level or 2), 4))
    if not evidence or not evidence.get("relationship_available"):
        return f"{prefix} 主题关系证据\n\n当前暂无足够 aligned canonical observations 生成主题关系证据。"
    semantic = evidence.get("semantic_overlap", {})
    headline = evidence.get("headline_state_evidence", {})
    structural = evidence.get("structural_regime_evidence", {})
    transitions = evidence.get("co_transition_evidence", {})
    return "\n".join(
        [
            f"{prefix} 主题关系证据",
            "",
            f"- 主题对：`{evidence.get('theme_pair')}`；source_mode：`{evidence.get('source_mode')}`；口径：`{evidence.get('calculation_mode')}`。",
            f"- aligned canonical observations：{evidence.get('aligned_observation_count', 0)}；alignment gaps：{evidence.get('alignment_gap_count', 0)}；分母为同一 source/mode/taxonomy lineage 下的 aligned canonical pair observations。",
            f"- 语义重叠：Jaccard {semantic.get('jaccard_overlap', 0.0)}；shared members {semantic.get('shared_member_count', 0)}；shared strict representatives {semantic.get('shared_strict_count', 0)}。",
            f"- headline 状态：exact agreement observed share {headline.get('exact_headline_state_agreement_share', 0.0)}；same-sign observed share {headline.get('same_sign_share', 0.0)}；opposing-sign observed share {headline.get('opposing_sign_share', 0.0)}。",
            f"- 结构签名：same-regime observed share {structural.get('same_regime_signature_share', 0.0)}；headline 对齐但结构签名不同 {structural.get('headline_aligned_regime_different_count', 0)} 次。",
            f"- co-transition：simultaneous headline changes {transitions.get('simultaneous_headline_change_count', 0)}；simultaneous structural changes {transitions.get('simultaneous_structural_change_count', 0)}。",
            "- 该证据只描述已对齐历史观察，不用于交易判断或未来走势推断。",
        ]
    )


def validate_theme_relationship_text(text: str) -> list[str]:
    content = str(text or "")
    return [word for word in RELATIONSHIP_FORBIDDEN_WORDS if word in content]
