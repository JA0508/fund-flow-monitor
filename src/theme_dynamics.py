from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.history_evidence import (
    build_historical_coverage_summary,
    build_historical_evidence_dimensions,
    build_snapshot_manifest,
    normalize_captured_time_bucket,
)
from src.analytical_continuity import (
    CONTINUITY_SEGMENT_COLUMN,
    attach_continuity_columns,
    build_continuity_summary,
    resolve_provider_contract_lineage,
)
from src.multi_day_trends import _latest_frame_for_date
from src.sample_data import SAMPLE_DIR, build_sample_snapshot_catalog, load_sample_snapshot_by_date
from src.snapshot_catalog import build_snapshot_catalog, load_snapshot_by_date
from src.theme_pool import THEME_MODE_LABELS, build_theme_snapshot_with_trace
from src.theme_radar import STATUS_SCORE
from src.theme_taxonomy import build_theme_definition_evidence, get_theme_names, load_theme_taxonomy


RAW_EVENT_OBSERVATION_GRAIN = (
    "snapshot_event_id",
    "theme_name",
    "calculation_mode",
    "source_mode",
    "theme_definition_fingerprint",
)

BUCKETED_ANALYTICAL_OBSERVATION_GRAIN = (
    "theme_name",
    "trade_date",
    "captured_time_bucket",
    "calculation_mode",
    "source_mode",
    CONTINUITY_SEGMENT_COLUMN,
    "taxonomy_fingerprint",
    "theme_definition_fingerprint",
)

THEME_OBSERVATION_GRAIN = BUCKETED_ANALYTICAL_OBSERVATION_GRAIN
THEME_DYNAMICS_MODES = ("strict_representative", "representative", "breadth")
DAILY_SELECTION_POLICY = "latest_snapshot_per_trade_date"
CAPTURED_TIME_BUCKET_MINUTES = 1
CANONICAL_BUCKET_POLICY = "latest_valid_snapshot_in_bucket"
DYNAMICS_DEFAULT_BASIS = "canonical_bucket_observations"
MEMBER_DOMINANCE_SHARE = 0.66
BALANCED_ABS_SHARE_DELTA = 0.20

FORBIDDEN_THEME_DYNAMICS_WORDS = (
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
    "win rate",
    "hit rate",
)


def _stable_id(payload: dict, length: int = 20) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def get_theme_observation_grain() -> tuple[str, ...]:
    return BUCKETED_ANALYTICAL_OBSERVATION_GRAIN


def get_raw_event_observation_grain() -> tuple[str, ...]:
    return RAW_EVENT_OBSERVATION_GRAIN


def get_bucketed_analytical_observation_grain() -> tuple[str, ...]:
    return BUCKETED_ANALYTICAL_OBSERVATION_GRAIN


def get_canonical_materialization_policy() -> str:
    return CANONICAL_BUCKET_POLICY


def normalize_theme_dynamics_mode(mode: str | None) -> str:
    value = str(mode or "").strip()
    if value in THEME_DYNAMICS_MODES:
        return value
    reverse = {label: key for key, label in THEME_MODE_LABELS.items()}
    return reverse.get(value, "strict_representative")


def _normalize_modes(modes: Iterable[str] | None) -> list[str]:
    if modes is None:
        return list(THEME_DYNAMICS_MODES)
    normalized = [normalize_theme_dynamics_mode(mode) for mode in modes]
    return list(dict.fromkeys(normalized)) or ["strict_representative"]


def _source_data_dir(source_mode: str, data_dir: str | None = None) -> str:
    if data_dir:
        return data_dir
    return SAMPLE_DIR if str(source_mode or "").upper() == "SAMPLE" else "data/ticks"


def _load_catalog(source_mode: str, data_dir: str) -> pd.DataFrame:
    return build_sample_snapshot_catalog(data_dir) if source_mode == "SAMPLE" else build_snapshot_catalog(data_dir)


def _load_snapshot(source_mode: str, trade_date: str, data_dir: str) -> pd.DataFrame:
    if source_mode == "SAMPLE":
        return load_sample_snapshot_by_date(trade_date, sample_dir=data_dir)
    return load_snapshot_by_date(trade_date, data_dir=data_dir)


def _industry_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if "sector_type" not in df.columns:
        return df.copy()
    industry = df[df["sector_type"].astype(str).eq("行业资金流")]
    return industry.copy() if not industry.empty else pd.DataFrame()


def _iter_captured_frames(df: pd.DataFrame) -> list[tuple[str | None, str | None, pd.DataFrame]]:
    industry = _industry_frame(df)
    if industry.empty:
        return []
    frames: list[tuple[str | None, str | None, pd.DataFrame]] = []
    if "captured_time" not in industry.columns:
        return [(None, None, industry.copy())]
    for captured_time, group in industry.groupby(industry["captured_time"].astype(str), sort=True):
        bucket = normalize_captured_time_bucket(captured_time)
        frames.append((str(captured_time), bucket, group.copy()))
    return frames


def _safe_first(frame: pd.DataFrame, column: str):
    if frame is None or frame.empty or column not in frame.columns:
        return None
    values = frame[column].dropna()
    if values.empty:
        return None
    value = values.iloc[0]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _state_group(status: object) -> str:
    score = STATUS_SCORE.get(str(status or "分歧/中性"), 0)
    if score > 0:
        return "positive"
    if score < 0:
        return "negative"
    return "neutral"


def _state_code(status: object) -> int:
    return int(STATUS_SCORE.get(str(status or "分歧/中性"), 0))


def _share(numerator: int | float, denominator: int | float) -> float:
    try:
        denom = float(denominator)
        if denom == 0:
            return 0.0
        return round(float(numerator) / denom, 4)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _manifest_by_date(manifest_df: pd.DataFrame) -> dict[str, dict]:
    if manifest_df is None or manifest_df.empty or "trade_date" not in manifest_df.columns:
        return {}
    out: dict[str, dict] = {}
    for _, row in manifest_df.sort_values(["trade_date", "captured_time"], na_position="last").iterrows():
        date = str(row.get("trade_date") or "")
        if date and date not in out:
            out[date] = row.to_dict()
    return out


def _relative_path_for_source(data_dir: str, trade_date: str, source_mode: str) -> str:
    path = Path(data_dir) / f"sector_flow_{trade_date}.csv"
    try:
        return path.resolve().relative_to(Path(data_dir).resolve()).as_posix()
    except ValueError:
        return path.name


def _snapshot_event_id(source_mode: str, relative_path: str, trade_date: str | None, captured_at: object, captured_time: object) -> str:
    return _stable_id(
        {
            "source_mode": str(source_mode or "SAMPLE").upper(),
            "relative_path": relative_path,
            "trade_date": trade_date or "unknown",
            "captured_at": "" if captured_at is None or pd.isna(captured_at) else str(captured_at),
            "captured_time": "" if captured_time is None or pd.isna(captured_time) else str(captured_time),
        }
    )


def _canonical_observation_id(row: pd.Series | dict, selected_event_id: str | None) -> str:
    payload = {
        "theme_name": row.get("theme_name"),
        "trade_date": row.get("trade_date"),
        "captured_time_bucket": row.get("captured_time_bucket"),
        "calculation_mode": row.get("calculation_mode"),
        "source_mode": row.get("source_mode"),
        CONTINUITY_SEGMENT_COLUMN: row.get(CONTINUITY_SEGMENT_COLUMN),
        "taxonomy_fingerprint": row.get("taxonomy_fingerprint"),
        "theme_definition_fingerprint": row.get("theme_definition_fingerprint"),
        "materialization_policy": CANONICAL_BUCKET_POLICY,
        "selected_event_observation_id": selected_event_id,
    }
    return _stable_id(payload)


def _sort_events(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    work["_captured_at_sort"] = pd.to_datetime(work.get("captured_at"), errors="coerce") if "captured_at" in work.columns else pd.NaT
    # captured_time is usually HH:MM:SS; string sorting is deterministic and avoids
    # parsing warnings for provider-specific timestamp fragments.
    work["_captured_time_sort"] = work["captured_time"].fillna("").astype(str) if "captured_time" in work.columns else ""
    sort_cols = [
        "trade_date",
        "captured_time_bucket",
        "_captured_at_sort",
        "_captured_time_sort",
        "event_observation_id",
    ]
    available = [column for column in sort_cols if column in work.columns]
    return work.sort_values(available, na_position="last").drop(columns=[c for c in ("_captured_at_sort", "_captured_time_sort") if c in work.columns])


def _is_event_valid(row: pd.Series | dict) -> bool:
    if "contract_ok" in row and pd.notna(row.get("contract_ok")):
        return bool(row.get("contract_ok"))
    status = str(row.get("contract_status") or "")
    return "通过" in status or "pass" in status.lower()


def _state_transition_count(states: list[int]) -> int:
    return int(sum(1 for index in range(1, len(states)) if states[index] != states[index - 1]))


def build_member_structural_divergence(member_traces: list[dict] | None) -> dict:
    members = [item for item in (member_traces or []) if item.get("included")]
    included = len(members)
    values = [float(item.get("input_value") or 0.0) for item in members]
    positive_values = [value for value in values if value > 0]
    negative_values = [value for value in values if value < 0]
    neutral_values = [value for value in values if value == 0]
    positive_total = round(sum(positive_values), 4)
    negative_total = round(sum(negative_values), 4)
    absolute_total = round(sum(abs(value) for value in values), 4)
    positive_abs_share = _share(sum(abs(value) for value in positive_values), absolute_total)
    negative_abs_share = _share(sum(abs(value) for value in negative_values), absolute_total)
    positive_count = len(positive_values)
    negative_count = len(negative_values)
    neutral_count = len(neutral_values)
    if included < 2:
        state = "insufficient_members"
    elif positive_count > 0 and negative_count == 0:
        state = "aligned_positive"
    elif negative_count > 0 and positive_count == 0:
        state = "aligned_negative"
    elif positive_abs_share >= MEMBER_DOMINANCE_SHARE:
        state = "mostly_positive"
    elif negative_abs_share >= MEMBER_DOMINANCE_SHARE:
        state = "mostly_negative"
    elif abs(positive_abs_share - negative_abs_share) <= BALANCED_ABS_SHARE_DELTA:
        state = "balanced_divergence"
    else:
        state = "mixed"
    return {
        "included_member_count": included,
        "positive_member_count": positive_count,
        "negative_member_count": negative_count,
        "neutral_member_count": neutral_count,
        "positive_member_share": _share(positive_count, included),
        "negative_member_share": _share(negative_count, included),
        "neutral_member_share": _share(neutral_count, included),
        "positive_value_total": positive_total,
        "negative_value_total": negative_total,
        "absolute_value_total": absolute_total,
        "positive_absolute_value_share": positive_abs_share,
        "negative_absolute_value_share": negative_abs_share,
        "neutral_absolute_value_share": _share(0, absolute_total),
        "member_sign_agreement": state,
        "structural_state": state,
        "dominance_threshold": MEMBER_DOMINANCE_SHARE,
        "balanced_abs_share_delta": BALANCED_ABS_SHARE_DELTA,
    }


def build_theme_observation_events(
    taxonomy: dict | None = None,
    source_mode: str = "SAMPLE",
    data_dir: str | None = None,
    calculation_modes: Iterable[str] | None = None,
    limit_dates: int | None = None,
    bucket_minutes: int = CAPTURED_TIME_BUCKET_MINUTES,
) -> pd.DataFrame:
    """Build raw theme observation events from physical cached snapshot captures.

    Raw event grain is snapshot_event_id × theme × calculation_mode × source_mode ×
    theme_definition_fingerprint. Time buckets are assigned later and are not part of
    raw event identity.
    """
    source_mode = str(source_mode or "SAMPLE").upper()
    if source_mode not in {"SAMPLE", "REAL"}:
        empty = pd.DataFrame()
        empty.attrs["warnings"] = ["source_mode 仅支持 SAMPLE 或 REAL。"]
        return empty
    taxonomy = taxonomy or load_theme_taxonomy()
    data_dir = _source_data_dir(source_mode, data_dir)
    modes = _normalize_modes(calculation_modes)
    catalog = _load_catalog(source_mode, data_dir)
    manifest = build_snapshot_manifest(data_dir=data_dir, source_mode=source_mode, bucket_minutes=bucket_minutes)
    manifest_lookup = _manifest_by_date(manifest)
    rows: list[dict] = []
    warnings: list[str] = []
    if catalog.empty:
        empty = pd.DataFrame()
        empty.attrs["warnings"] = [f"{source_mode} 快照目录暂无可用 CSV。"]
        empty.attrs["manifest"] = manifest
        return empty
    work_catalog = catalog.copy()
    if "is_readable" in work_catalog.columns:
        work_catalog = work_catalog[work_catalog["is_readable"].fillna(False)]
    if "snapshot_date" not in work_catalog.columns or work_catalog.empty:
        empty = pd.DataFrame()
        empty.attrs["warnings"] = [f"{source_mode} 快照目录暂无可读 snapshot_date。"]
        empty.attrs["manifest"] = manifest
        return empty
    work_catalog = work_catalog.sort_values("snapshot_date")
    if limit_dates is not None:
        work_catalog = work_catalog.tail(max(1, int(limit_dates)))
    definition_cache: dict[str, dict] = {}
    for _, catalog_row in work_catalog.iterrows():
        trade_date = str(catalog_row.get("snapshot_date") or "")
        if not trade_date:
            continue
        snapshot_df = _load_snapshot(source_mode, trade_date, data_dir)
        industry = _industry_frame(snapshot_df)
        if industry.empty:
            warnings.append(f"{trade_date}: 缺少可用行业资金流 snapshot event。")
            continue
        if "captured_at" in industry.columns and pd.to_datetime(industry["captured_at"], errors="coerce").notna().any():
            group_key = pd.to_datetime(industry["captured_at"], errors="coerce")
        elif "captured_time" in industry.columns:
            group_key = industry["captured_time"].astype(str)
        else:
            group_key = pd.Series(["single_event"] * len(industry), index=industry.index)
        lineage = manifest_lookup.get(trade_date, {})
        relative_path = lineage.get("relative_path") or _relative_path_for_source(data_dir, trade_date, source_mode)
        for _, event_frame in industry.groupby(group_key, dropna=False, sort=True):
            captured_at = _safe_first(event_frame, "captured_at")
            captured_time_values = event_frame["captured_time"].dropna().astype(str).tolist() if "captured_time" in event_frame.columns else []
            captured_time = sorted({value for value in captured_time_values if value.strip()})[-1] if captured_time_values else None
            captured_bucket = normalize_captured_time_bucket(captured_time, bucket_minutes=bucket_minutes)
            snapshot_event_id = _snapshot_event_id(source_mode, str(relative_path), trade_date, captured_at, captured_time)
            for mode in modes:
                try:
                    theme_df, trace_map = build_theme_snapshot_with_trace(event_frame, theme_mode=mode)
                except Exception as exc:
                    warnings.append(f"{trade_date} {captured_time or '--'} {mode}: 主题快照构建失败：{type(exc).__name__}")
                    continue
                if theme_df.empty:
                    warnings.append(f"{trade_date} {captured_time or '--'} {mode}: 主题快照为空。")
                    continue
                for _, theme_row in theme_df.iterrows():
                    theme_name = str(theme_row.get("theme_name") or theme_row.get("sector_name") or "")
                    if not theme_name:
                        continue
                    definition = definition_cache.get(theme_name)
                    if definition is None:
                        definition = build_theme_definition_evidence(taxonomy, theme_name)
                        definition_cache[theme_name] = definition
                    trace = trace_map.get(theme_name, {})
                    member_structure = build_member_structural_divergence(trace.get("all_members", []))
                    continuity = resolve_provider_contract_lineage(
                        {
                            "source_mode": source_mode,
                            "provider": _safe_first(event_frame, "provider") or lineage.get("provider"),
                            "provider_id": _safe_first(event_frame, "provider_id") or lineage.get("provider_id"),
                            "api_name": _safe_first(event_frame, "api_name") or lineage.get("api_name"),
                            "sector_type": _safe_first(event_frame, "sector_type") or lineage.get("sector_type"),
                            "data_mode": _safe_first(event_frame, "data_mode") or lineage.get("data_mode") or source_mode,
                            "provider_contract_id": _safe_first(event_frame, "provider_contract_id") or lineage.get("provider_contract_id"),
                            "provider_contract_fingerprint": _safe_first(event_frame, "provider_contract_fingerprint") or lineage.get("provider_contract_fingerprint"),
                        },
                        source_mode=source_mode,
                    )
                    event_payload = {
                        "snapshot_event_id": snapshot_event_id,
                        "theme_name": theme_name,
                        "calculation_mode": mode,
                        "source_mode": source_mode,
                        "theme_definition_fingerprint": definition.get("theme_definition_fingerprint"),
                    }
                    rows.append(
                        {
                            "event_observation_id": _stable_id(event_payload),
                            "observation_id": _stable_id(event_payload),
                            "snapshot_event_id": snapshot_event_id,
                            "file_snapshot_id": lineage.get("snapshot_id"),
                            "snapshot_id": snapshot_event_id,
                            "relative_path": relative_path,
                            "theme_name": theme_name,
                            "theme_id": definition.get("theme_id") or theme_name,
                            "trade_date": trade_date,
                            "captured_at": captured_at,
                            "captured_time": captured_time,
                            "captured_time_bucket": captured_bucket,
                            "calculation_mode": mode,
                            "calculation_mode_label": THEME_MODE_LABELS.get(mode, mode),
                            "source_mode": source_mode,
                            "taxonomy_fingerprint": definition.get("taxonomy_fingerprint"),
                            "theme_definition_fingerprint": definition.get("theme_definition_fingerprint"),
                            "aggregate_value": float(theme_row.get("main_net_inflow_billion") or 0.0),
                            "theme_score": None,
                            "derived_state": theme_row.get("theme_status"),
                            "derived_state_level": theme_row.get("theme_status_level"),
                            "state_code": _state_code(theme_row.get("theme_status")),
                            "state_group": _state_group(theme_row.get("theme_status")),
                            "matched_member_count": int(trace.get("matched_member_count", theme_row.get("source_sector_count") or 0) or 0),
                            "configured_member_count": int(trace.get("configured_member_count", 0) or 0),
                            "provider": _safe_first(event_frame, "provider") or lineage.get("provider"),
                            "provider_id": _safe_first(event_frame, "provider_id") or lineage.get("provider_id"),
                            "api_name": _safe_first(event_frame, "api_name") or lineage.get("api_name"),
                            "provider_contract_id": continuity.get("provider_contract_id"),
                            "provider_contract_fingerprint": continuity.get("provider_contract_fingerprint"),
                            "provider_contract_resolution_state": continuity.get("provider_contract_resolution_state"),
                            "provider_contract_resolution_label": continuity.get("provider_contract_resolution_label"),
                            CONTINUITY_SEGMENT_COLUMN: continuity.get(CONTINUITY_SEGMENT_COLUMN),
                            "upstream_origin": _safe_first(event_frame, "upstream_origin") or lineage.get("upstream_origin"),
                            "data_mode": _safe_first(event_frame, "data_mode") or lineage.get("data_mode") or source_mode,
                            "schema_fingerprint": lineage.get("schema_fingerprint"),
                            "contract_status": lineage.get("contract_status"),
                            "contract_ok": bool(lineage.get("contract_ok")) if lineage else None,
                            "positive_member_count": member_structure["positive_member_count"],
                            "negative_member_count": member_structure["negative_member_count"],
                            "neutral_member_count": member_structure["neutral_member_count"],
                            "included_member_count": member_structure["included_member_count"],
                            "member_sign_agreement": member_structure["member_sign_agreement"],
                            "member_structural_state": member_structure["structural_state"],
                            "member_structure": member_structure,
                            "member_traces": trace.get("all_members", []),
                            "match_strategy": theme_row.get("match_strategy"),
                        }
                    )
    if not rows:
        empty = pd.DataFrame()
        empty.attrs["warnings"] = warnings or [f"{source_mode} 未生成 raw theme observation events。"]
        empty.attrs["manifest"] = manifest
        return empty
    events = _sort_events(pd.DataFrame(rows)).reset_index(drop=True)
    duplicate_mask = events.duplicated(list(RAW_EVENT_OBSERVATION_GRAIN), keep=False)
    duplicate_count = int(duplicate_mask.sum())
    events["true_duplicate_event_grain"] = duplicate_mask
    if duplicate_count:
        warnings.append(f"检测到 {duplicate_count} 条 true raw event-grain duplicate rows，未静默覆盖。")
    events.attrs["warnings"] = warnings
    events.attrs["manifest"] = manifest
    events.attrs["raw_event_grain"] = RAW_EVENT_OBSERVATION_GRAIN
    events.attrs["true_duplicate_event_row_count"] = duplicate_count
    events.attrs["bucket_minutes"] = max(1, int(bucket_minutes or 1))
    return events


def analyze_observation_bucket_collisions(events_df: pd.DataFrame) -> pd.DataFrame:
    if events_df is None or events_df.empty:
        return pd.DataFrame()
    events_df = attach_continuity_columns(events_df)
    rows: list[dict] = []
    for key_values, group in events_df.groupby(list(BUCKETED_ANALYTICAL_OBSERVATION_GRAIN), dropna=False, sort=True):
        base = dict(zip(BUCKETED_ANALYTICAL_OBSERVATION_GRAIN, key_values, strict=False))
        ordered = _sort_events(group).reset_index(drop=True)
        event_count = int(len(ordered))
        event_ids = ordered["event_observation_id"].dropna().astype(str).tolist()
        snapshot_ids = ordered["snapshot_event_id"].dropna().astype(str).tolist()
        state_codes = ordered["state_code"].dropna().astype(int).tolist() if "state_code" in ordered.columns else []
        true_duplicate_rows = int(ordered.get("true_duplicate_event_grain", pd.Series(False, index=ordered.index)).fillna(False).sum())
        transition_count = _state_transition_count(state_codes)
        if event_count <= 1:
            collision_type = "single_event"
        elif true_duplicate_rows and true_duplicate_rows == event_count:
            collision_type = "true_duplicate_event"
        elif true_duplicate_rows:
            collision_type = "mixed_collision"
        else:
            collision_type = "multiple_events_same_bucket"
        captured_at_values = ordered["captured_at"].dropna().astype(str).tolist() if "captured_at" in ordered.columns else []
        captured_time_values = ordered["captured_time"].dropna().astype(str).tolist() if "captured_time" in ordered.columns else []
        aggregate_values = pd.to_numeric(ordered["aggregate_value"], errors="coerce") if "aggregate_value" in ordered.columns else pd.Series(dtype=float)
        rows.append(
            {
                **base,
                "event_count": event_count,
                "event_observation_ids": event_ids,
                "snapshot_ids": snapshot_ids,
                "file_snapshot_ids": ordered["file_snapshot_id"].dropna().astype(str).tolist() if "file_snapshot_id" in ordered.columns else [],
                "provider_contract_ids": ordered["provider_contract_id"].dropna().astype(str).unique().tolist() if "provider_contract_id" in ordered.columns else [],
                "provider_contract_resolution_states": ordered["provider_contract_resolution_state"].dropna().astype(str).unique().tolist() if "provider_contract_resolution_state" in ordered.columns else [],
                "analytical_continuity_segment_ids": ordered[CONTINUITY_SEGMENT_COLUMN].dropna().astype(str).unique().tolist() if CONTINUITY_SEGMENT_COLUMN in ordered.columns else [],
                "exact_captured_times": captured_time_values,
                "first_captured_at": min(captured_at_values) if captured_at_values else None,
                "latest_captured_at": max(captured_at_values) if captured_at_values else None,
                "state_codes_represented": sorted(set(state_codes)),
                "distinct_state_count": int(len(set(state_codes))),
                "state_transition_count_within_bucket": transition_count,
                "aggregate_values_represented": [float(value) for value in aggregate_values.dropna().tolist()],
                "aggregate_value_min": float(aggregate_values.min()) if not aggregate_values.dropna().empty else None,
                "aggregate_value_max": float(aggregate_values.max()) if not aggregate_values.dropna().empty else None,
                "true_duplicate_event_count": true_duplicate_rows,
                "collision_type": collision_type,
                "within_bucket_state_stable": bool(len(set(state_codes)) <= 1),
            }
        )
    return pd.DataFrame(rows).sort_values(["theme_name", "trade_date", "captured_time_bucket", "calculation_mode"], na_position="last").reset_index(drop=True)


def build_bucket_collision_summary(collision_df: pd.DataFrame) -> dict:
    if collision_df is None or collision_df.empty:
        return {
            "bucket_count": 0,
            "collided_bucket_count": 0,
            "collision_event_count": 0,
            "extra_events_within_collided_buckets": 0,
            "max_events_per_bucket": 0,
            "within_bucket_state_change_count": 0,
            "collision_type_counts": {},
        }
    collided = collision_df[collision_df["event_count"].fillna(0).astype(int) > 1]
    return {
        "bucket_count": int(len(collision_df)),
        "collided_bucket_count": int(len(collided)),
        "collision_event_count": int(collided["event_count"].sum()) if not collided.empty else 0,
        "extra_events_within_collided_buckets": int((collided["event_count"] - 1).sum()) if not collided.empty else 0,
        "max_events_per_bucket": int(collision_df["event_count"].max()) if not collision_df.empty else 0,
        "collision_count_by_date": collided.groupby("trade_date").size().astype(int).to_dict() if not collided.empty else {},
        "collision_count_by_mode": collided.groupby("calculation_mode").size().astype(int).to_dict() if not collided.empty else {},
        "within_bucket_state_change_count": int((collision_df["distinct_state_count"].fillna(0).astype(int) > 1).sum()),
        "collision_type_counts": collision_df["collision_type"].value_counts().astype(int).to_dict(),
    }


def _select_canonical_event(group: pd.DataFrame, policy: str = CANONICAL_BUCKET_POLICY) -> pd.Series:
    """Select the canonical event for one bucketed analytical grain.

    Default policy uses the latest valid snapshot in a minute bucket because the
    AKShare "今日" sector-flow path is treated by this project as a cumulative
    as-of-capture snapshot. Ties are resolved by deterministic event ID ordering.
    Invalid contract events are excluded when any valid event exists; if all events
    are invalid, the latest event is retained only so lineage remains inspectable.
    """
    ordered = _sort_events(group).reset_index(drop=True)
    if ordered.empty:
        return pd.Series(dtype=object)
    valid = ordered[ordered.apply(_is_event_valid, axis=1)]
    candidates = valid if not valid.empty else ordered
    if policy == "earliest_valid_snapshot_in_bucket":
        return candidates.iloc[0]
    return candidates.iloc[-1]


def materialize_canonical_observations(
    events_df: pd.DataFrame,
    policy: str = CANONICAL_BUCKET_POLICY,
) -> pd.DataFrame:
    if events_df is None or events_df.empty:
        empty = pd.DataFrame()
        empty.attrs["materialization_policy"] = policy
        empty.attrs["dynamics_basis"] = DYNAMICS_DEFAULT_BASIS
        empty.attrs["bucket_collision_summary"] = build_bucket_collision_summary(pd.DataFrame())
        return empty
    events_df = attach_continuity_columns(events_df)
    collision_df = analyze_observation_bucket_collisions(events_df)
    collision_lookup = {
        tuple(row.get(column) for column in BUCKETED_ANALYTICAL_OBSERVATION_GRAIN): row.to_dict()
        for _, row in collision_df.iterrows()
    }
    rows: list[dict] = []
    for key_values, group in events_df.groupby(list(BUCKETED_ANALYTICAL_OBSERVATION_GRAIN), dropna=False, sort=True):
        selected = _select_canonical_event(group, policy=policy)
        if selected.empty:
            continue
        collision = collision_lookup.get(tuple(key_values), {})
        selected_event_id = str(selected.get("event_observation_id") or "")
        canonical_id = _canonical_observation_id(selected, selected_event_id)
        event_count = int(collision.get("event_count", len(group)) or 0)
        distinct_state_count = int(collision.get("distinct_state_count", 0) or 0)
        state_codes = collision.get("state_codes_represented") or []
        row = selected.to_dict()
        row.update(
            {
                "canonical_observation_id": canonical_id,
                "observation_id": canonical_id,
                "selected_event_observation_id": selected_event_id,
                "selected_snapshot_id": selected.get("snapshot_event_id"),
                "selected_captured_at": selected.get("captured_at"),
                "selected_captured_time": selected.get("captured_time"),
                "selected_aggregate_value": selected.get("aggregate_value"),
                "selected_state": selected.get("derived_state"),
                "selected_state_code": selected.get("state_code"),
                "selected_event_valid": bool(_is_event_valid(selected)),
                "materialization_policy": policy,
                "materialization_status": "selected_valid_event" if _is_event_valid(selected) else "no_valid_event_selected_for_lineage",
                "event_count": event_count,
                "contributing_event_observation_ids": collision.get("event_observation_ids") or group["event_observation_id"].dropna().astype(str).tolist(),
                "contributing_snapshot_ids": collision.get("snapshot_ids") or group["snapshot_event_id"].dropna().astype(str).tolist(),
                "first_captured_at": collision.get("first_captured_at"),
                "latest_captured_at": collision.get("latest_captured_at"),
                "distinct_state_count": distinct_state_count,
                "state_codes_represented": state_codes,
                "within_bucket_state_stable": bool(collision.get("within_bucket_state_stable", distinct_state_count <= 1)),
                "state_transition_count_within_bucket": int(collision.get("state_transition_count_within_bucket", 0) or 0),
                "bucket_stability_state": "single_event" if event_count <= 1 else ("state_stable" if distinct_state_count <= 1 else "state_changed_within_bucket"),
                "aggregate_value_min": collision.get("aggregate_value_min"),
                "aggregate_value_max": collision.get("aggregate_value_max"),
                "collision_type": collision.get("collision_type", "single_event"),
                "dynamics_basis": DYNAMICS_DEFAULT_BASIS,
            }
        )
        rows.append(row)
    canonical = pd.DataFrame(rows)
    if canonical.empty:
        canonical.attrs["materialization_policy"] = policy
        canonical.attrs["bucket_collision_summary"] = build_bucket_collision_summary(collision_df)
        return canonical
    canonical = canonical.sort_values(["source_mode", "theme_name", "trade_date", "captured_time_bucket", "calculation_mode"], na_position="last").reset_index(drop=True)
    canonical.attrs["materialization_policy"] = policy
    canonical.attrs["dynamics_basis"] = DYNAMICS_DEFAULT_BASIS
    canonical.attrs["raw_event_count"] = int(len(events_df))
    canonical.attrs["bucket_collision_table"] = collision_df
    canonical.attrs["bucket_collision_summary"] = build_bucket_collision_summary(collision_df)
    canonical.attrs["analytical_grain"] = BUCKETED_ANALYTICAL_OBSERVATION_GRAIN
    canonical.attrs["raw_event_grain"] = RAW_EVENT_OBSERVATION_GRAIN
    canonical.attrs["continuity_summary"] = build_continuity_summary(events_df)
    canonical.attrs["true_duplicate_event_row_count"] = int(getattr(events_df, "attrs", {}).get("true_duplicate_event_row_count", 0) or 0)
    canonical.attrs["warnings"] = list(getattr(events_df, "attrs", {}).get("warnings", []))
    canonical.attrs["manifest"] = getattr(events_df, "attrs", {}).get("manifest", pd.DataFrame())
    canonical.attrs["daily_selection_policy"] = DAILY_SELECTION_POLICY
    return canonical


def build_theme_observation_cube(
    taxonomy: dict | None = None,
    source_mode: str = "SAMPLE",
    data_dir: str | None = None,
    calculation_modes: Iterable[str] | None = None,
    limit_dates: int | None = None,
    bucket_minutes: int = CAPTURED_TIME_BUCKET_MINUTES,
) -> pd.DataFrame:
    events = build_theme_observation_events(
        taxonomy=taxonomy,
        source_mode=source_mode,
        data_dir=data_dir,
        calculation_modes=calculation_modes,
        limit_dates=limit_dates,
        bucket_minutes=bucket_minutes,
    )
    canonical = materialize_canonical_observations(events, policy=CANONICAL_BUCKET_POLICY)
    if canonical.empty:
        canonical.attrs["warnings"] = list(getattr(events, "attrs", {}).get("warnings", []))
        canonical.attrs["manifest"] = getattr(events, "attrs", {}).get("manifest", pd.DataFrame())
        return canonical
    summary = canonical.attrs.get("bucket_collision_summary", {})
    warnings = list(canonical.attrs.get("warnings", []))
    collided_count = int(summary.get("collided_bucket_count", 0) or 0)
    if collided_count:
        warnings.append(f"检测到 {collided_count} 个 time-bucket collision；已按 {CANONICAL_BUCKET_POLICY} 物化 canonical observations，并保留 contributing lineage。")
    canonical.attrs["warnings"] = warnings
    canonical.attrs["duplicate_grain_count"] = 0
    canonical.attrs["bucket_minutes"] = max(1, int(bucket_minutes or 1))
    return canonical


def _filter_series(cube_df: pd.DataFrame, theme_name: str | None = None, calculation_mode: str | None = None, source_mode: str | None = None) -> pd.DataFrame:
    if cube_df is None or cube_df.empty:
        return pd.DataFrame()
    df = cube_df.copy()
    if theme_name:
        df = df[df["theme_name"].astype(str).eq(str(theme_name))]
    if calculation_mode:
        mode = normalize_theme_dynamics_mode(calculation_mode)
        df = df[df["calculation_mode"].astype(str).eq(mode)]
    if source_mode:
        df = df[df["source_mode"].astype(str).str.upper().eq(str(source_mode).upper())]
    return df.sort_values(["trade_date", "captured_time_bucket", "calculation_mode"], na_position="last").reset_index(drop=True)


def _longest_streak(values: list[str], target_group: str | None = None) -> int:
    best = 0
    current = 0
    previous = object()
    for value in values:
        comparable = _state_group(value) if target_group else value
        target = target_group if target_group else previous
        if target_group:
            current = current + 1 if comparable == target else 0
        else:
            current = current + 1 if value == previous else 1
            previous = value
        best = max(best, current)
    return int(best)


def build_state_transition_trace(observations_df: pd.DataFrame) -> dict:
    if observations_df is None or observations_df.empty:
        return {
            "trace_available": False,
            "observation_count": 0,
            "state_path": [],
            "transition_count": 0,
            "state_counts": {},
            "state_occupancy_share": {},
            "warnings": ["暂无可用主题动态观察。"],
        }
    df = observations_df.sort_values(["trade_date", "captured_time_bucket"], na_position="last").reset_index(drop=True)
    states = df["derived_state"].fillna("分歧/中性").astype(str).tolist()
    groups = [_state_group(state) for state in states]
    observation_count = len(states)
    transitions = [(states[i - 1], states[i]) for i in range(1, len(states)) if states[i] != states[i - 1]]
    unchanged = max(0, observation_count - 1 - len(transitions))
    counts = dict(Counter(states))
    group_counts = dict(Counter(groups))
    return {
        "trace_available": True,
        "observation_count": int(observation_count),
        "first_state": states[0] if states else None,
        "latest_state": states[-1] if states else None,
        "state_path": states,
        "state_path_text": " → ".join(states),
        "transition_count": int(len(transitions)),
        "unchanged_step_count": int(unchanged),
        "distinct_state_count": int(len(counts)),
        "latest_transition": transitions[-1] if transitions else None,
        "state_counts": counts,
        "state_occupancy_share": {state: _share(count, observation_count) for state, count in counts.items()},
        "positive_state_count": int(group_counts.get("positive", 0)),
        "neutral_state_count": int(group_counts.get("neutral", 0)),
        "negative_state_count": int(group_counts.get("negative", 0)),
        "positive_state_share": _share(group_counts.get("positive", 0), observation_count),
        "neutral_state_share": _share(group_counts.get("neutral", 0), observation_count),
        "negative_state_share": _share(group_counts.get("negative", 0), observation_count),
        "longest_positive_streak": _longest_streak(states, "positive"),
        "longest_neutral_streak": _longest_streak(states, "neutral"),
        "longest_negative_streak": _longest_streak(states, "negative"),
        "longest_same_state_streak": _longest_streak(states),
        "observed_date_count": int(df["trade_date"].dropna().astype(str).nunique()),
        "observed_time_bucket_count": int(df["captured_time_bucket"].dropna().astype(str).nunique()),
        "denominator_note": "state_occupancy_share = canonical bucket observations / total canonical bucket observations.",
    }


def select_daily_observations(observations_df: pd.DataFrame) -> pd.DataFrame:
    if observations_df is None or observations_df.empty:
        return pd.DataFrame()
    rows = []
    df = observations_df.sort_values(["trade_date", "captured_time_bucket"], na_position="last")
    for _, group in df.groupby("trade_date", sort=True):
        rows.append(group.iloc[-1].to_dict())
    return pd.DataFrame(rows).reset_index(drop=True)


def build_cross_date_state_evolution(observations_df: pd.DataFrame) -> dict:
    daily = select_daily_observations(observations_df)
    trace = build_state_transition_trace(daily)
    return {
        "daily_evolution_available": bool(not daily.empty),
        "daily_selection_policy": DAILY_SELECTION_POLICY,
        "dates_represented": daily["trade_date"].dropna().astype(str).tolist() if not daily.empty else [],
        "selected_observations": daily,
        "daily_state_path": trace.get("state_path", []),
        "daily_state_path_text": trace.get("state_path_text", ""),
        "daily_transition_count": int(trace.get("transition_count", 0) or 0),
        "first_daily_state": trace.get("first_state"),
        "latest_daily_state": trace.get("latest_state"),
        "latest_daily_transition": trace.get("latest_transition"),
        "state_counts_by_date": trace.get("state_counts", {}),
        "taxonomy_fingerprint_consistency": int(daily["taxonomy_fingerprint"].dropna().astype(str).nunique()) <= 1 if not daily.empty else True,
        "schema_fingerprint_consistency": int(daily["schema_fingerprint"].dropna().astype(str).nunique()) <= 1 if not daily.empty else True,
    }


def classify_scope_divergence(row: pd.Series) -> str:
    available = int(row.get("available_scope_count", 0) or 0)
    if available < 2:
        return "insufficient_scopes"
    states = [row.get(f"{mode}_state") for mode in THEME_DYNAMICS_MODES if row.get(f"{mode}_state")]
    groups = [_state_group(state) for state in states]
    if len(set(states)) == 1:
        group = groups[0] if groups else "neutral"
        return f"aligned_{group}"
    if len(set(groups)) == 1:
        return "mixed_same_sign"
    rep_group = _state_group(row.get("representative_state")) if row.get("representative_state") else None
    breadth_group = _state_group(row.get("breadth_state")) if row.get("breadth_state") else None
    if rep_group == "positive" and breadth_group == "negative":
        return "representative_positive_breadth_negative"
    if rep_group == "negative" and breadth_group == "positive":
        return "representative_negative_breadth_positive"
    return "mixed_direction"


def build_scope_divergence_table(cube_df: pd.DataFrame) -> pd.DataFrame:
    if cube_df is None or cube_df.empty:
        return pd.DataFrame()
    cube_df = attach_continuity_columns(cube_df)
    keys = [
        "theme_name",
        "trade_date",
        "captured_time_bucket",
        "source_mode",
        CONTINUITY_SEGMENT_COLUMN,
        "taxonomy_fingerprint",
        "theme_definition_fingerprint",
    ]
    rows = []
    for key_values, group in cube_df.groupby(keys, dropna=False, sort=True):
        base = dict(zip(keys, key_values, strict=False))
        row = dict(base)
        codes = []
        groups = []
        compared_snapshot_ids = []
        compared_event_ids = []
        for mode in THEME_DYNAMICS_MODES:
            item = group[group["calculation_mode"].astype(str).eq(mode)]
            if item.empty:
                row[f"{mode}_state"] = None
                row[f"{mode}_aggregate_value"] = None
                continue
            first = item.iloc[0]
            state = first.get("derived_state")
            code = _state_code(state)
            row[f"{mode}_state"] = state
            row[f"{mode}_aggregate_value"] = first.get("aggregate_value")
            selected_snapshot_id = first.get("selected_snapshot_id") or first.get("snapshot_event_id") or first.get("snapshot_id")
            selected_event_id = first.get("selected_event_observation_id") or first.get("event_observation_id")
            row[f"{mode}_selected_snapshot_id"] = selected_snapshot_id
            row[f"{mode}_selected_event_observation_id"] = selected_event_id
            if selected_snapshot_id:
                compared_snapshot_ids.append(str(selected_snapshot_id))
            if selected_event_id:
                compared_event_ids.append(str(selected_event_id))
            codes.append(code)
            groups.append(_state_group(state))
        row["available_scope_count"] = int(len(codes))
        row["compared_snapshot_ids"] = compared_snapshot_ids
        row["compared_event_observation_ids"] = compared_event_ids
        row["compared_continuity_segment_ids"] = group[CONTINUITY_SEGMENT_COLUMN].dropna().astype(str).unique().tolist() if CONTINUITY_SEGMENT_COLUMN in group.columns else []
        row["aligned_snapshot_id_consistent"] = bool(len(set(compared_snapshot_ids)) == 1 and compared_snapshot_ids)
        if row["available_scope_count"] < 2:
            row["alignment_status"] = "insufficient_scopes"
        elif row["aligned_snapshot_id_consistent"]:
            row["alignment_status"] = "fully_aligned"
        elif compared_snapshot_ids:
            row["alignment_status"] = "bucket_aligned_different_snapshots"
        else:
            row["alignment_status"] = "lineage_incompatible"
        row["state_code_min"] = min(codes) if codes else None
        row["state_code_max"] = max(codes) if codes else None
        row["state_code_range"] = (max(codes) - min(codes)) if codes else None
        row["all_scopes_equal"] = bool(len({row.get(f"{mode}_state") for mode in THEME_DYNAMICS_MODES if row.get(f"{mode}_state")}) == 1 and codes)
        row["state_sign_agreement"] = bool(len(set(groups)) == 1 and groups)
        row["positive_scope_count"] = int(groups.count("positive"))
        row["neutral_scope_count"] = int(groups.count("neutral"))
        row["negative_scope_count"] = int(groups.count("negative"))
        row["scope_divergence_state"] = classify_scope_divergence(pd.Series(row))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["theme_name", "trade_date", "captured_time_bucket"], na_position="last").reset_index(drop=True)


def _latest_scope_divergence(scope_df: pd.DataFrame, theme_name: str) -> dict:
    if scope_df is None or scope_df.empty:
        return {"scope_divergence_available": False, "scope_divergence_state": "insufficient_scopes"}
    theme_scope = scope_df[scope_df["theme_name"].astype(str).eq(str(theme_name))].copy()
    if theme_scope.empty:
        return {"scope_divergence_available": False, "scope_divergence_state": "insufficient_scopes"}
    latest = theme_scope.sort_values(["trade_date", "captured_time_bucket"], na_position="last").iloc[-1].to_dict()
    latest["scope_divergence_available"] = True
    return latest


def _lineage_incompatibilities(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    for column, label in (
        ("source_mode", "source mode"),
        (CONTINUITY_SEGMENT_COLUMN, "analytical continuity segment"),
        ("taxonomy_fingerprint", "taxonomy fingerprint"),
        ("theme_definition_fingerprint", "theme-definition fingerprint"),
    ):
        if column in df.columns and df[column].dropna().astype(str).nunique() > 1:
            warnings.append(f"检测到多个 {label}，未静默合并为单一动态序列。")
    return warnings


def build_theme_dynamics_evidence(
    cube_df: pd.DataFrame | None = None,
    theme_name: str | None = None,
    source_mode: str = "SAMPLE",
    calculation_mode: str = "strict_representative",
    taxonomy: dict | None = None,
    data_dir: str | None = None,
) -> dict:
    source_mode = str(source_mode or "SAMPLE").upper()
    taxonomy = taxonomy or load_theme_taxonomy()
    if cube_df is None:
        cube_df = build_theme_observation_cube(taxonomy=taxonomy, source_mode=source_mode, data_dir=data_dir)
    available_themes = sorted(cube_df["theme_name"].dropna().astype(str).unique().tolist()) if cube_df is not None and not cube_df.empty else get_theme_names(taxonomy)
    selected_theme = theme_name or (available_themes[0] if available_themes else "")
    mode = normalize_theme_dynamics_mode(calculation_mode)
    series = _filter_series(cube_df, selected_theme, mode, source_mode)
    warnings = list(getattr(cube_df, "attrs", {}).get("warnings", [])) if cube_df is not None else []
    if source_mode == "SAMPLE":
        warnings.append("当前动态证据来自 SAMPLE 合成演示数据，不代表真实行情。")
    warnings.extend(_lineage_incompatibilities(series))
    lineage_compatible = not _lineage_incompatibilities(series)
    state_trace = build_state_transition_trace(series if lineage_compatible else pd.DataFrame())
    daily_evolution = build_cross_date_state_evolution(series if lineage_compatible else pd.DataFrame())
    scope_table = build_scope_divergence_table(cube_df if cube_df is not None else pd.DataFrame())
    latest_scope = _latest_scope_divergence(scope_table, selected_theme)
    latest_member = {}
    if not series.empty and lineage_compatible:
        latest_row = series.sort_values(["trade_date", "captured_time_bucket"], na_position="last").iloc[-1]
        latest_member = latest_row.get("member_structure") or {}
    manifest = getattr(cube_df, "attrs", {}).get("manifest", pd.DataFrame()) if cube_df is not None else pd.DataFrame()
    bucket_collision_summary = getattr(cube_df, "attrs", {}).get("bucket_collision_summary", {}) if cube_df is not None else {}
    materialization_policy = getattr(cube_df, "attrs", {}).get("materialization_policy", CANONICAL_BUCKET_POLICY) if cube_df is not None else CANONICAL_BUCKET_POLICY
    dynamics_basis = getattr(cube_df, "attrs", {}).get("dynamics_basis", DYNAMICS_DEFAULT_BASIS) if cube_df is not None else DYNAMICS_DEFAULT_BASIS
    raw_event_count = int(getattr(cube_df, "attrs", {}).get("raw_event_count", len(cube_df) if cube_df is not None else 0) or 0)
    history_summary = build_historical_coverage_summary(manifest)
    history_dimensions = build_historical_evidence_dimensions(history_summary)
    schema_counts = series["schema_fingerprint"].dropna().astype(str).value_counts().to_dict() if not series.empty and "schema_fingerprint" in series.columns else {}
    if len(schema_counts) > 1:
        warnings.append("观察序列包含多个 schema fingerprint；已按事实展示，不视为自动失效。")
    return {
        "dynamics_available": bool(not series.empty and lineage_compatible),
        "theme_name": selected_theme,
        "source_mode": source_mode,
        "calculation_mode": mode,
        "calculation_mode_label": THEME_MODE_LABELS.get(mode, mode),
        "raw_event_grain": RAW_EVENT_OBSERVATION_GRAIN,
        "analytical_grain": BUCKETED_ANALYTICAL_OBSERVATION_GRAIN,
        "dynamics_basis": dynamics_basis,
        "materialization_policy": materialization_policy,
        "bucket_minutes": int(getattr(cube_df, "attrs", {}).get("bucket_minutes", CAPTURED_TIME_BUCKET_MINUTES) or CAPTURED_TIME_BUCKET_MINUTES) if cube_df is not None else CAPTURED_TIME_BUCKET_MINUTES,
        "raw_event_observation_count": raw_event_count,
        "canonical_observation_count": int(len(cube_df)) if cube_df is not None else 0,
        "bucket_collision_summary": bucket_collision_summary,
        "observation_count": int(len(series)) if lineage_compatible else 0,
        "trade_date_count": int(series["trade_date"].dropna().astype(str).nunique()) if not series.empty and lineage_compatible else 0,
        "captured_time_bucket_count": int(series["captured_time_bucket"].dropna().astype(str).nunique()) if not series.empty and lineage_compatible else 0,
        "taxonomy_fingerprint": None if series.empty else series["taxonomy_fingerprint"].dropna().astype(str).iloc[0],
        "theme_definition_fingerprint": None if series.empty else series["theme_definition_fingerprint"].dropna().astype(str).iloc[0],
        "state_transition_trace": state_trace,
        "cross_date_state_evolution": daily_evolution,
        "scope_divergence_summary": latest_scope,
        "latest_member_structural_divergence": latest_member,
        "history_span_state": history_dimensions.get("history_span_state"),
        "intraday_depth_state": history_dimensions.get("intraday_depth_state"),
        "coverage_consistency_state": history_dimensions.get("coverage_consistency_state"),
        "schema_fingerprint_counts": schema_counts,
        "schema_consistent": len(schema_counts) <= 1,
        "lineage_compatible": lineage_compatible,
        "warnings": list(dict.fromkeys(str(item) for item in warnings if item)),
    }


def render_theme_dynamics_brief_section(evidence: dict, heading_level: int = 2) -> str:
    hashes = "#" * max(1, min(int(heading_level or 2), 4))
    if not evidence or not evidence.get("dynamics_available"):
        return f"{hashes} 主题动态证据\n\n暂无可用主题动态证据。"
    trace = evidence.get("state_transition_trace", {})
    scope = evidence.get("scope_divergence_summary", {})
    member = evidence.get("latest_member_structural_divergence", {})
    collisions = evidence.get("bucket_collision_summary") or {}
    lines = [
        f"{hashes} 主题动态证据",
        "",
        f"- 主题：{evidence.get('theme_name')}；来源：{evidence.get('source_mode')}；口径：{evidence.get('calculation_mode_label')}",
        f"- 动态依据：{evidence.get('dynamics_basis') or DYNAMICS_DEFAULT_BASIS}；物化策略：{evidence.get('materialization_policy') or CANONICAL_BUCKET_POLICY}。",
        f"- 观察粒度：`theme × trade_date × captured_time_bucket × calculation_mode × source_mode × taxonomy_definition`。",
        f"- 时间桶证据：raw events {evidence.get('raw_event_observation_count', 0)}；canonical observations {evidence.get('canonical_observation_count', 0)}；collided buckets {collisions.get('collided_bucket_count', 0)}。",
        f"- 观测点：{evidence.get('observation_count')}；覆盖日期：{evidence.get('trade_date_count')}；状态路径：{trace.get('state_path_text') or '--'}。",
        f"- 状态占用：正向 {trace.get('positive_state_count', 0)} / 中性 {trace.get('neutral_state_count', 0)} / 负向 {trace.get('negative_state_count', 0)}，分母为 canonical bucket observations。",
        f"- 最新 scope divergence：{scope.get('scope_divergence_state') or '--'}。",
        f"- 最新成员结构：{member.get('member_sign_agreement') or '--'}；included members：{member.get('included_member_count', 0)}。",
        "- 以上只描述已缓存快照中的历史状态占用与结构分化，不作为预测口径，不预测未来走势，不构成投资建议。",
    ]
    if evidence.get("source_mode") == "SAMPLE":
        lines.append("- SAMPLE 说明：该动态证据来自合成演示数据，不代表真实行情。")
    return "\n".join(lines)


def validate_theme_dynamics_text(text: str) -> list[str]:
    value = str(text or "")
    return [word for word in FORBIDDEN_THEME_DYNAMICS_WORDS if word in value]
