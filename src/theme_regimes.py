from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Iterable

import pandas as pd

from src.theme_dynamics import (
    BUCKETED_ANALYTICAL_OBSERVATION_GRAIN,
    CANONICAL_BUCKET_POLICY,
    DYNAMICS_DEFAULT_BASIS,
    THEME_DYNAMICS_MODES,
    build_scope_divergence_table,
    build_theme_observation_cube,
    normalize_theme_dynamics_mode,
)


REGIME_SIGNATURE_DIMENSIONS = (
    "headline_state",
    "scope_divergence_state",
    "member_divergence_state",
)
REGIME_OBSERVATION_BASIS = DYNAMICS_DEFAULT_BASIS
REGIME_CANONICAL_POLICY = CANONICAL_BUCKET_POLICY
OBSERVED_SHARE_DENOMINATOR = "canonical observations within the selected group"

FORBIDDEN_THEME_REGIME_WORDS = (
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
    "probability",
    "likelihood",
    "reversal signal",
    "early warning",
    "leading signal",
)


def _stable_id(payload: dict, length: int = 16) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _safe_str(value: object, fallback: str = "unknown") -> str:
    if value is None:
        return fallback
    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text or fallback


def _lineage_warnings(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    for column, label in (
        ("source_mode", "source mode"),
        ("taxonomy_fingerprint", "taxonomy fingerprint"),
        ("theme_definition_fingerprint", "theme-definition fingerprint"),
        ("calculation_mode", "calculation mode"),
    ):
        if column in df.columns and df[column].dropna().astype(str).nunique() > 1:
            warnings.append(f"检测到多个 {label}；结构状态序列按 lineage 分组处理，不静默合并。")
    return warnings


def get_regime_signature_dimensions() -> tuple[str, ...]:
    return REGIME_SIGNATURE_DIMENSIONS


def get_regime_observation_basis() -> str:
    return REGIME_OBSERVATION_BASIS


def build_regime_signature_record(
    observation: dict | pd.Series,
    scope_divergence_state: str | None = None,
    member_divergence_state: str | None = None,
) -> dict:
    row = observation.to_dict() if isinstance(observation, pd.Series) else dict(observation or {})
    headline_state = _safe_str(row.get("derived_state") or row.get("selected_state"), "unknown")
    headline_code = row.get("state_code")
    if headline_code is None or pd.isna(headline_code):
        headline_code = row.get("selected_state_code")
    scope_state = _safe_str(scope_divergence_state or row.get("scope_divergence_state"), "insufficient_scopes")
    member_state = _safe_str(
        member_divergence_state
        or row.get("member_divergence_state")
        or row.get("member_structural_state")
        or row.get("member_sign_agreement"),
        "unknown",
    )
    signature = f"{headline_state}|{scope_state}|{member_state}"
    availability = {
        "headline_state": headline_state != "unknown",
        "scope_divergence_state": scope_state not in {"unknown", ""},
        "member_divergence_state": member_state not in {"unknown", ""},
    }
    lineage = {
        "source_mode": _safe_str(row.get("source_mode"), "unknown"),
        "theme_name": _safe_str(row.get("theme_name"), "unknown"),
        "calculation_mode": _safe_str(row.get("calculation_mode"), "unknown"),
        "taxonomy_fingerprint": _safe_str(row.get("taxonomy_fingerprint"), "unknown"),
        "theme_definition_fingerprint": _safe_str(row.get("theme_definition_fingerprint"), "unknown"),
    }
    signature_id = _stable_id({**lineage, "regime_signature": signature})
    return {
        "regime_signature": signature,
        "regime_signature_id": signature_id,
        "headline_state": headline_state,
        "headline_state_code": None if headline_code is None or pd.isna(headline_code) else int(headline_code),
        "scope_divergence_state": scope_state,
        "member_divergence_state": member_state,
        "component_availability": availability,
        "component_availability_label": ", ".join(
            key for key, available in availability.items() if available
        )
        or "none",
        "calculation_basis": REGIME_OBSERVATION_BASIS,
        "materialization_policy": REGIME_CANONICAL_POLICY,
        **lineage,
    }


def attach_regime_signatures_to_observations(
    cube_df: pd.DataFrame,
    calculation_mode: str | None = "strict_representative",
) -> pd.DataFrame:
    if cube_df is None or cube_df.empty:
        empty = pd.DataFrame()
        empty.attrs["warnings"] = ["暂无 canonical observations 可用于结构状态签名。"]
        empty.attrs["regime_observation_basis"] = REGIME_OBSERVATION_BASIS
        return empty

    mode = normalize_theme_dynamics_mode(calculation_mode) if calculation_mode else None
    observations = cube_df.copy()
    if mode:
        observations = observations[observations["calculation_mode"].astype(str).eq(mode)].copy()
    if observations.empty:
        empty = pd.DataFrame()
        empty.attrs["warnings"] = [f"暂无 {mode or 'ALL'} 口径 canonical observations。"]
        empty.attrs["regime_observation_basis"] = REGIME_OBSERVATION_BASIS
        return empty

    scope_df = build_scope_divergence_table(cube_df)
    merge_keys = [
        "theme_name",
        "trade_date",
        "captured_time_bucket",
        "source_mode",
        "taxonomy_fingerprint",
        "theme_definition_fingerprint",
    ]
    scope_columns = [
        "scope_divergence_state",
        "alignment_status",
        "available_scope_count",
        "compared_snapshot_ids",
        "compared_event_observation_ids",
        "aligned_snapshot_id_consistent",
    ]
    available_scope_columns = merge_keys + [column for column in scope_columns if column in scope_df.columns]
    if not scope_df.empty:
        observations = observations.merge(
            scope_df[available_scope_columns],
            on=merge_keys,
            how="left",
            suffixes=("", "_scope"),
        )
    else:
        observations["scope_divergence_state"] = "insufficient_scopes"
        observations["alignment_status"] = "insufficient_scopes"
        observations["available_scope_count"] = 0

    rows: list[dict] = []
    for _, observation in observations.iterrows():
        member_state = observation.get("member_structural_state")
        if not member_state or pd.isna(member_state):
            member_structure = observation.get("member_structure")
            if isinstance(member_structure, dict):
                member_state = member_structure.get("structural_state") or member_structure.get("member_sign_agreement")
        record = build_regime_signature_record(
            observation,
            scope_divergence_state=observation.get("scope_divergence_state"),
            member_divergence_state=member_state,
        )
        item = observation.to_dict()
        item.update(record)
        item["canonical_observation_id"] = observation.get("canonical_observation_id") or observation.get("observation_id")
        item["selected_snapshot_id"] = observation.get("selected_snapshot_id") or observation.get("snapshot_event_id") or observation.get("snapshot_id")
        item["selected_event_observation_id"] = observation.get("selected_event_observation_id") or observation.get("event_observation_id")
        rows.append(item)

    result = pd.DataFrame(rows)
    sort_cols = [column for column in ("theme_name", "source_mode", "taxonomy_fingerprint", "theme_definition_fingerprint", "trade_date", "captured_time_bucket", "calculation_mode") if column in result.columns]
    if sort_cols:
        result = result.sort_values(sort_cols, na_position="last").reset_index(drop=True)
    result.attrs["regime_observation_basis"] = REGIME_OBSERVATION_BASIS
    result.attrs["materialization_policy"] = REGIME_CANONICAL_POLICY
    result.attrs["warnings"] = list(getattr(cube_df, "attrs", {}).get("warnings", []))
    result.attrs["analytical_grain"] = BUCKETED_ANALYTICAL_OBSERVATION_GRAIN
    return result


def filter_regime_observations(
    regime_df: pd.DataFrame,
    theme_name: str | None = None,
    source_mode: str | None = None,
    calculation_mode: str | None = None,
    headline_state: str | None = None,
) -> pd.DataFrame:
    if regime_df is None or regime_df.empty:
        return pd.DataFrame()
    df = regime_df.copy()
    if theme_name:
        df = df[df["theme_name"].astype(str).eq(str(theme_name))]
    if source_mode:
        df = df[df["source_mode"].astype(str).str.upper().eq(str(source_mode).upper())]
    if calculation_mode:
        mode = normalize_theme_dynamics_mode(calculation_mode)
        df = df[df["calculation_mode"].astype(str).eq(mode)]
    if headline_state:
        df = df[df["headline_state"].astype(str).eq(str(headline_state))]
    return df.sort_values(["trade_date", "captured_time_bucket", "canonical_observation_id"], na_position="last").reset_index(drop=True)


def _lineage_group_columns(df: pd.DataFrame) -> list[str]:
    return [
        column
        for column in ("theme_name", "source_mode", "calculation_mode", "taxonomy_fingerprint", "theme_definition_fingerprint")
        if column in df.columns
    ]


def _chronological(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    sort_cols = [column for column in ("trade_date", "captured_time_bucket", "selected_captured_at", "selected_captured_time", "canonical_observation_id") if column in df.columns]
    return df.sort_values(sort_cols, na_position="last").reset_index(drop=True)


def build_regime_episodes(regime_df: pd.DataFrame, theme_name: str | None = None) -> pd.DataFrame:
    df = filter_regime_observations(regime_df, theme_name=theme_name)
    if df.empty:
        empty = pd.DataFrame()
        empty.attrs["warnings"] = ["暂无结构状态签名 observation 可生成 episodes。"]
        return empty

    rows: list[dict] = []
    group_cols = _lineage_group_columns(df)
    for lineage_values, group in df.groupby(group_cols, dropna=False, sort=True):
        lineage = dict(zip(group_cols, lineage_values if isinstance(lineage_values, tuple) else (lineage_values,), strict=False))
        ordered = _chronological(group)
        episode_rows: list[pd.DataFrame] = []
        start_idx = 0
        signatures = ordered["regime_signature"].astype(str).tolist()
        for idx in range(1, len(ordered)):
            if signatures[idx] != signatures[idx - 1]:
                episode_rows.append(ordered.iloc[start_idx:idx])
                start_idx = idx
        episode_rows.append(ordered.iloc[start_idx:])
        for episode_index, episode in enumerate(episode_rows):
            first = episode.iloc[0]
            last = episode.iloc[-1]
            payload = {
                **lineage,
                "regime_signature_id": first.get("regime_signature_id"),
                "start_observation_id": first.get("canonical_observation_id"),
                "end_observation_id": last.get("canonical_observation_id"),
                "episode_index": episode_index,
            }
            previous_signature = episode_rows[episode_index - 1].iloc[0].get("regime_signature") if episode_index > 0 else None
            next_signature = episode_rows[episode_index + 1].iloc[0].get("regime_signature") if episode_index < len(episode_rows) - 1 else None
            snapshot_ids = []
            for value in episode.get("selected_snapshot_id", pd.Series(dtype=object)).dropna().astype(str).tolist():
                snapshot_ids.append(value)
            rows.append(
                {
                    "episode_id": _stable_id(payload),
                    **lineage,
                    "regime_signature": first.get("regime_signature"),
                    "regime_signature_id": first.get("regime_signature_id"),
                    "headline_state": first.get("headline_state"),
                    "scope_divergence_state": first.get("scope_divergence_state"),
                    "member_divergence_state": first.get("member_divergence_state"),
                    "start_observation_id": first.get("canonical_observation_id"),
                    "end_observation_id": last.get("canonical_observation_id"),
                    "start_trade_date": first.get("trade_date"),
                    "end_trade_date": last.get("trade_date"),
                    "start_captured_at": first.get("selected_captured_at") or first.get("captured_time_bucket"),
                    "end_captured_at": last.get("selected_captured_at") or last.get("captured_time_bucket"),
                    "canonical_observation_count": int(len(episode)),
                    "distinct_trade_date_count": int(episode["trade_date"].dropna().astype(str).nunique()) if "trade_date" in episode.columns else 0,
                    "contributing_snapshot_count": int(len(set(snapshot_ids))),
                    "previous_regime_signature": previous_signature,
                    "next_regime_signature": next_signature,
                    "observed_timestamp_span_label": f"{first.get('trade_date')} {first.get('captured_time_bucket')} → {last.get('trade_date')} {last.get('captured_time_bucket')}",
                    "span_semantics": "observed timestamp span, not continuous regime duration",
                }
            )
    episodes = pd.DataFrame(rows)
    if episodes.empty:
        return episodes
    return episodes.sort_values(["theme_name", "source_mode", "start_trade_date", "start_captured_at"], na_position="last").reset_index(drop=True)


def build_headline_preserving_structural_transitions(regime_df: pd.DataFrame) -> pd.DataFrame:
    if regime_df is None or regime_df.empty:
        return pd.DataFrame()
    rows: list[dict] = []
    for _, group in regime_df.groupby(_lineage_group_columns(regime_df), dropna=False, sort=True):
        ordered = _chronological(group)
        for idx in range(1, len(ordered)):
            previous = ordered.iloc[idx - 1]
            current = ordered.iloc[idx]
            same_headline = str(previous.get("headline_state")) == str(current.get("headline_state"))
            same_signature = str(previous.get("regime_signature")) == str(current.get("regime_signature"))
            if same_headline and not same_signature:
                rows.append(
                    {
                        "transition_type": "headline_preserving_structural_transition",
                        "theme_name": current.get("theme_name"),
                        "source_mode": current.get("source_mode"),
                        "calculation_mode": current.get("calculation_mode"),
                        "headline_state": current.get("headline_state"),
                        "from_observation_id": previous.get("canonical_observation_id"),
                        "to_observation_id": current.get("canonical_observation_id"),
                        "from_regime_signature": previous.get("regime_signature"),
                        "to_regime_signature": current.get("regime_signature"),
                        "from_scope_structure": previous.get("scope_divergence_state"),
                        "to_scope_structure": current.get("scope_divergence_state"),
                        "from_member_structure": previous.get("member_divergence_state"),
                        "to_member_structure": current.get("member_divergence_state"),
                        "scope_structure_changed": str(previous.get("scope_divergence_state")) != str(current.get("scope_divergence_state")),
                        "member_structure_changed": str(previous.get("member_divergence_state")) != str(current.get("member_divergence_state")),
                        "from_trade_date": previous.get("trade_date"),
                        "to_trade_date": current.get("trade_date"),
                        "from_captured_time_bucket": previous.get("captured_time_bucket"),
                        "to_captured_time_bucket": current.get("captured_time_bucket"),
                        "from_selected_snapshot_id": previous.get("selected_snapshot_id"),
                        "to_selected_snapshot_id": current.get("selected_snapshot_id"),
                        "explanation": (
                            f"headline state remained {current.get('headline_state')}; "
                            f"scope structure {previous.get('scope_divergence_state')} → {current.get('scope_divergence_state')}; "
                            f"member structure {previous.get('member_divergence_state')} → {current.get('member_divergence_state')}."
                        ),
                    }
                )
    return pd.DataFrame(rows)


def build_regime_transition_trace(regime_df: pd.DataFrame) -> dict:
    if regime_df is None or regime_df.empty:
        return {
            "trace_available": False,
            "observation_count": 0,
            "episode_count": 0,
            "regime_signature_count": 0,
            "warnings": ["暂无结构状态签名 observation 可生成 transition trace。"],
        }
    warnings = _lineage_warnings(regime_df)
    episodes = build_regime_episodes(regime_df)
    transition_pairs: Counter = Counter()
    regime_path: list[str] = []
    episode_path: list[str] = episodes["regime_signature"].astype(str).tolist() if not episodes.empty else []
    regime_transition_count = 0
    unchanged_steps = 0
    headline_state_change_count = 0
    structural_change_count = 0
    headline_preserving_count = 0
    structural_with_headline_count = 0
    latest_transition = None
    previous_signature = None
    latest_signature = None
    for _, group in regime_df.groupby(_lineage_group_columns(regime_df), dropna=False, sort=True):
        ordered = _chronological(group)
        signatures = ordered["regime_signature"].astype(str).tolist()
        regime_path.extend(signatures)
        for idx in range(1, len(ordered)):
            prev = ordered.iloc[idx - 1]
            cur = ordered.iloc[idx]
            same_signature = str(prev.get("regime_signature")) == str(cur.get("regime_signature"))
            same_headline = str(prev.get("headline_state")) == str(cur.get("headline_state"))
            if same_signature:
                unchanged_steps += 1
            else:
                structural_change_count += 1
                regime_transition_count += 1
                pair = (str(prev.get("regime_signature")), str(cur.get("regime_signature")))
                transition_pairs[pair] += 1
                latest_transition = pair
                if same_headline:
                    headline_preserving_count += 1
                else:
                    structural_with_headline_count += 1
            if not same_headline:
                headline_state_change_count += 1
        if signatures:
            previous_signature = signatures[-2] if len(signatures) >= 2 else previous_signature
            latest_signature = signatures[-1]
    pair_counts = {f"{left} -> {right}": int(count) for (left, right), count in transition_pairs.items()}
    headline_preserving = build_headline_preserving_structural_transitions(regime_df)
    return {
        "trace_available": True,
        "observation_count": int(len(regime_df)),
        "episode_count": int(len(episodes)),
        "regime_signature_count": int(regime_df["regime_signature"].dropna().astype(str).nunique()),
        "regime_path": regime_path,
        "episode_path": episode_path,
        "regime_transition_count": int(regime_transition_count),
        "unchanged_signature_step_count": int(unchanged_steps),
        "transition_pair_counts": pair_counts,
        "latest_regime_signature": latest_signature,
        "previous_regime_signature": previous_signature,
        "latest_regime_transition": latest_transition,
        "headline_state_change_count": int(headline_state_change_count),
        "structural_change_count": int(structural_change_count),
        "headline_preserving_structural_change_count": int(headline_preserving_count),
        "structural_change_with_headline_change_count": int(structural_with_headline_count),
        "headline_preserving_structural_transitions": headline_preserving.to_dict(orient="records") if not headline_preserving.empty else [],
        "observed_transition_denominator": "adjacent canonical observations within compatible lineage groups",
        "warnings": warnings,
    }


def build_state_equivalent_structural_analysis(
    regime_df: pd.DataFrame,
    headline_state: str | None = None,
) -> dict:
    if regime_df is None or regime_df.empty:
        return {
            "analysis_available": False,
            "headline_state": headline_state,
            "observation_count": 0,
            "warnings": ["暂无结构状态签名 observation 可做同 headline state 结构对照。"],
        }
    df = regime_df.copy()
    if headline_state:
        df = df[df["headline_state"].astype(str).eq(str(headline_state))]
    if df.empty:
        return {
            "analysis_available": False,
            "headline_state": headline_state,
            "observation_count": 0,
            "warnings": [f"未找到 headline state={headline_state} 的 canonical observations。"],
        }
    signature_counts = df["regime_signature"].astype(str).value_counts().to_dict()
    observation_count = int(len(df))
    transitions = build_headline_preserving_structural_transitions(df)
    state_label = str(headline_state or (df["headline_state"].dropna().astype(str).iloc[0] if df["headline_state"].dropna().size else "ALL"))
    signature_share = {key: round(count / observation_count, 4) for key, count in signature_counts.items()}
    structure_count = int(len(signature_counts))
    return {
        "analysis_available": True,
        "headline_state": state_label,
        "observation_count": observation_count,
        "distinct_regime_signature_count": structure_count,
        "state_equivalent_structure_count": structure_count,
        "regime_signature_counts": signature_counts,
        "regime_signature_observed_shares": signature_share,
        "dominant_observed_signature": max(signature_counts.items(), key=lambda item: item[1])[0] if signature_counts else None,
        "headline_preserving_structural_transition_count": int(len(transitions)),
        "scope_structure_counts": df["scope_divergence_state"].astype(str).value_counts().to_dict(),
        "member_structure_counts": df["member_divergence_state"].astype(str).value_counts().to_dict(),
        "structurally_homogeneous": bool(structure_count == 1),
        "structurally_heterogeneous": bool(structure_count > 1),
        "homogeneous_definition": "one observed structural signature under this headline state",
        "heterogeneous_definition": "more than one observed structural signature under this headline state",
        "observed_share_denominator": OBSERVED_SHARE_DENOMINATOR,
        "warnings": _lineage_warnings(df),
    }


def compare_state_equivalent_observations(
    first_observation: dict | pd.Series,
    second_observation: dict | pd.Series,
) -> dict:
    first = first_observation.to_dict() if isinstance(first_observation, pd.Series) else dict(first_observation or {})
    second = second_observation.to_dict() if isinstance(second_observation, pd.Series) else dict(second_observation or {})
    same_headline = str(first.get("headline_state")) == str(second.get("headline_state"))
    same_signature = str(first.get("regime_signature")) == str(second.get("regime_signature"))
    taxonomy_compatible = str(first.get("taxonomy_fingerprint")) == str(second.get("taxonomy_fingerprint"))
    source_compatible = str(first.get("source_mode")) == str(second.get("source_mode"))
    theme_definition_compatible = str(first.get("theme_definition_fingerprint")) == str(second.get("theme_definition_fingerprint"))
    return {
        "comparison_available": bool(same_headline and taxonomy_compatible and source_compatible and theme_definition_compatible),
        "comparison_status": "state_equivalent_comparison" if same_headline else "headline_state_mismatch",
        "same_headline_state": bool(same_headline),
        "same_regime_signature": bool(same_signature),
        "scope_structure_changed": str(first.get("scope_divergence_state")) != str(second.get("scope_divergence_state")),
        "member_structure_changed": str(first.get("member_divergence_state")) != str(second.get("member_divergence_state")),
        "taxonomy_lineage_compatible": bool(taxonomy_compatible),
        "source_mode_compatible": bool(source_compatible),
        "theme_definition_lineage_compatible": bool(theme_definition_compatible),
        "from_observation_id": first.get("canonical_observation_id"),
        "to_observation_id": second.get("canonical_observation_id"),
        "from_trade_date": first.get("trade_date"),
        "to_trade_date": second.get("trade_date"),
        "from_captured_time_bucket": first.get("captured_time_bucket"),
        "to_captured_time_bucket": second.get("captured_time_bucket"),
        "from_selected_snapshot_id": first.get("selected_snapshot_id"),
        "to_selected_snapshot_id": second.get("selected_snapshot_id"),
        "from_regime_signature": first.get("regime_signature"),
        "to_regime_signature": second.get("regime_signature"),
        "component_differences": {
            "headline_state": (first.get("headline_state"), second.get("headline_state")),
            "scope_divergence_state": (first.get("scope_divergence_state"), second.get("scope_divergence_state")),
            "member_divergence_state": (first.get("member_divergence_state"), second.get("member_divergence_state")),
        },
    }


def build_theme_regime_evidence(
    theme_name: str,
    source_mode: str = "SAMPLE",
    calculation_mode: str = "strict_representative",
    taxonomy: dict | None = None,
    data_dir: str | None = None,
    cube_df: pd.DataFrame | None = None,
) -> dict:
    source_mode = str(source_mode or "SAMPLE").upper()
    mode = normalize_theme_dynamics_mode(calculation_mode)
    cube = cube_df if cube_df is not None else build_theme_observation_cube(
        taxonomy=taxonomy,
        source_mode=source_mode,
        data_dir=data_dir,
        calculation_modes=THEME_DYNAMICS_MODES,
    )
    regime_all = attach_regime_signatures_to_observations(cube, calculation_mode=mode)
    series = filter_regime_observations(regime_all, theme_name=theme_name, source_mode=source_mode, calculation_mode=mode)
    warnings = list(getattr(regime_all, "attrs", {}).get("warnings", []))
    if source_mode == "SAMPLE":
        warnings.append("当前结构状态签名来自 SAMPLE 合成演示数据，不代表真实行情。")
    warnings.extend(_lineage_warnings(series))
    episodes = build_regime_episodes(series)
    transition_trace = build_regime_transition_trace(series)
    latest = _chronological(series).iloc[-1].to_dict() if not series.empty else {}
    headline_state = latest.get("headline_state")
    state_equivalent = build_state_equivalent_structural_analysis(series, headline_state=headline_state) if headline_state else {}
    return {
        "regime_available": bool(not series.empty),
        "theme_name": theme_name,
        "source_mode": source_mode,
        "calculation_mode": mode,
        "canonical_observation_basis": REGIME_OBSERVATION_BASIS,
        "materialization_policy": REGIME_CANONICAL_POLICY,
        "signature_dimensions": REGIME_SIGNATURE_DIMENSIONS,
        "canonical_observation_count": int(len(series)),
        "regime_signature_count": int(series["regime_signature"].dropna().astype(str).nunique()) if not series.empty else 0,
        "episode_count": int(len(episodes)),
        "latest_regime_signature": latest.get("regime_signature"),
        "latest_regime_signature_id": latest.get("regime_signature_id"),
        "latest_headline_state": latest.get("headline_state"),
        "latest_scope_divergence_state": latest.get("scope_divergence_state"),
        "latest_member_divergence_state": latest.get("member_divergence_state"),
        "taxonomy_fingerprint": latest.get("taxonomy_fingerprint"),
        "theme_definition_fingerprint": latest.get("theme_definition_fingerprint"),
        "regime_observations": series,
        "episodes": episodes,
        "transition_trace": transition_trace,
        "state_equivalent_analysis": state_equivalent,
        "warnings": list(dict.fromkeys(str(item) for item in warnings if item)),
    }


def render_theme_regime_brief_section(evidence: dict, heading_level: int = 2) -> str:
    hashes = "#" * max(1, min(int(heading_level or 2), 4))
    if not evidence or not evidence.get("regime_available"):
        return f"{hashes} 结构状态签名证据\n\n暂无可用结构状态签名证据。"
    transition = evidence.get("transition_trace") or {}
    state_equiv = evidence.get("state_equivalent_analysis") or {}
    lines = [
        f"{hashes} 结构状态签名证据",
        "",
        f"- 主题：{evidence.get('theme_name')}；来源：{evidence.get('source_mode')}；口径：{evidence.get('calculation_mode')}。",
        f"- 签名维度：headline state / scope structure / member structure；依据：{evidence.get('canonical_observation_basis')}；物化策略：{evidence.get('materialization_policy')}。",
        f"- 最新结构签名：`{evidence.get('latest_regime_signature')}`。",
        f"- canonical observations：{evidence.get('canonical_observation_count')}；结构签名数：{evidence.get('regime_signature_count')}；episodes：{evidence.get('episode_count')}。",
        f"- 已观测结构切换：{transition.get('structural_change_count', 0)}；headline 不变但结构变化：{transition.get('headline_preserving_structural_change_count', 0)}。",
        f"- 当前 headline state `{evidence.get('latest_headline_state')}` 下已观测结构签名数：{state_equiv.get('distinct_regime_signature_count', 0)}，observed share 分母为该 headline state 下的 canonical observations。",
        "- 以上仅描述已缓存历史样本中的结构状态，不预测未来走势，不构成投资建议。",
    ]
    if evidence.get("source_mode") == "SAMPLE":
        lines.append("- 当前为 SAMPLE 合成演示数据，不代表真实行情。")
    return "\n".join(lines)


def validate_theme_regime_text(text: str) -> list[str]:
    value = str(text or "")
    return [word for word in FORBIDDEN_THEME_REGIME_WORDS if word in value]

