from __future__ import annotations

import hashlib
import json
from datetime import datetime, time
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.analytical_continuity import (
    CONTINUITY_SEGMENT_COLUMN,
    CONTRACT_FINGERPRINT_COLUMN,
    CONTRACT_ID_COLUMN,
    CONTRACT_RESOLUTION_COLUMN,
    resolve_provider_contract_lineage,
)
from src.analytical_eligibility import (
    WORKLOAD_THEME_CONTINUITY,
    evaluate_observation_eligibility,
)
from src.collection_policy import get_default_collection_policy, parse_policy_time
from src.data_contracts import validate_real_snapshot_dataframe, validate_sample_snapshot_dataframe
from src.market_session_policy import (
    STATE_ELIGIBLE,
    STATE_INELIGIBLE,
    STATE_UNVERIFIED,
    evaluate_market_session_date,
    get_default_market_session_policy,
)
from src.provider_contracts import UNKNOWN
from src.sample_data import SAMPLE_DIR


DEFAULT_ACQUISITION_CELL_MINUTES = 30
FRAME_BOUNDARY_CONVENTION = "[start, end); final session endpoint included"

ASSIGNMENT_ASSIGNED = "assigned_to_cell"
ASSIGNMENT_OUTSIDE = "outside_configured_session"
ASSIGNMENT_MISSING_TIME = "missing_capture_time"
ASSIGNMENT_INVALID_TIME = "ambiguous_or_invalid_time"
ASSIGNMENT_DATE_INELIGIBLE = STATE_INELIGIBLE
ASSIGNMENT_CALENDAR_UNVERIFIED = STATE_UNVERIFIED

CONTRIBUTION_NEW_CELL = "new_cell_coverage"
CONTRIBUTION_ADDITIONAL = "additional_capture_in_existing_cell"
CONTRIBUTION_OUTSIDE = "outside_acquisition_frame"
CONTRIBUTION_EXCLUDED = "excluded_from_qualified_accumulation"


FORBIDDEN_EVIDENCE_ACCUMULATION_WORDS = (
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
    "quality score",
    "confidence score",
    "coverage score",
)


def _stable_id(payload: dict, length: int = 20) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _source_data_dir(source_mode: str, data_dir: str | None = None) -> str:
    if data_dir:
        return str(data_dir)
    return SAMPLE_DIR if str(source_mode or "").upper() == "SAMPLE" else "data/ticks"


def _safe_relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.name


def _safe_first(frame: pd.DataFrame, column: str, fallback: object = UNKNOWN) -> object:
    if frame is None or frame.empty or column not in frame.columns:
        return fallback
    values = frame[column].dropna()
    if values.empty:
        return fallback
    value = values.iloc[0]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _normalize_source(source_mode: str | None) -> str:
    value = str(source_mode or "REAL").upper()
    return "SAMPLE" if value == "SAMPLE" else "REAL"


def _parse_time(value: object) -> time | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parts = text.split(":")
        if len(parts) == 2:
            text = f"{text}:00"
        return time.fromisoformat(text)
    except ValueError:
        return None


def _time_to_seconds(value: time) -> int:
    return value.hour * 3600 + value.minute * 60 + value.second


def _contract_report_for_group(group: pd.DataFrame, source_mode: str) -> dict:
    if source_mode == "SAMPLE":
        return validate_sample_snapshot_dataframe(group, context="physical_capture_event")
    return validate_real_snapshot_dataframe(group, context="physical_capture_event")


def build_physical_capture_event_inventory(
    data_dir: str | Path | None = None,
    source_mode: str = "REAL",
    market_session_policy: dict | None = None,
) -> pd.DataFrame:
    """Return one row per physical provider snapshot capture.

    A physical capture event is identified by source mode, relative CSV path,
    trade date and captured_time. Sector rows, theme rows and calculation modes
    must not multiply this inventory.
    """

    source = _normalize_source(source_mode)
    date_policy = market_session_policy or get_default_market_session_policy()
    directory = Path(_source_data_dir(source, str(data_dir) if data_dir is not None else None))
    if not directory.exists():
        return pd.DataFrame()

    rows: list[dict] = []
    for path in sorted(directory.glob("sector_flow_*.csv")):
        if not path.is_file():
            continue
        relative_path = _safe_relpath(path, directory)
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if df.empty:
            continue
        if "captured_time" in df.columns:
            grouped = df.groupby(df["captured_time"].fillna("").astype(str), dropna=False, sort=True)
        else:
            grouped = [(None, df)]
        for captured_time, group in grouped:
            capture_group = group.copy()
            if capture_group.empty:
                continue
            trade_date = str(_safe_first(capture_group, "trade_date", path.stem.replace("sector_flow_", "")) or "")
            captured_time_text = None if captured_time is None else str(captured_time or "").strip()
            captured_at = _safe_first(capture_group, "captured_at", None)
            contract_report = _contract_report_for_group(capture_group, source)
            lineage = resolve_provider_contract_lineage(_safe_first_row(capture_group), source_mode=source)
            date_decision = evaluate_market_session_date(trade_date, date_policy)
            event_payload = {
                "source_mode": source,
                "relative_path": relative_path,
                "trade_date": trade_date,
                "captured_time": captured_time_text or "",
                "captured_at": "" if captured_at is None else str(captured_at),
            }
            capture_event_id = _stable_id(event_payload)
            base = {
                "capture_event_id": capture_event_id,
                "source_mode": source,
                "trade_date": trade_date,
                "captured_time": captured_time_text,
                "captured_at": captured_at,
                "relative_path": relative_path,
                "file_name": path.name,
                "row_count": int(len(capture_group)),
                "sector_row_count": int(capture_group["sector_name"].nunique()) if "sector_name" in capture_group.columns else int(len(capture_group)),
                "provider": _safe_first(capture_group, "provider"),
                "provider_id": _safe_first(capture_group, "provider_id"),
                "api_name": _safe_first(capture_group, "api_name"),
                "data_mode": _safe_first(capture_group, "data_mode", source),
                "contract_ok": bool(contract_report.get("contract_ok")),
                "contract_label": contract_report.get("contract_label"),
                "contract_error_count": int(contract_report.get("error_count", 0) or 0),
                "contract_warning_count": int(contract_report.get("warning_count", 0) or 0),
            }
            base.update(lineage)
            eligibility = evaluate_observation_eligibility(base, workload=WORKLOAD_THEME_CONTINUITY)
            market_date_ok = source == "SAMPLE" or bool(date_decision.get("is_market_session_date_eligible"))
            base.update(
                {
                    "calendar_date": date_decision.get("calendar_date"),
                    "market_session_date_state": date_decision.get("market_session_date_state"),
                    "is_market_session_date_eligible": bool(date_decision.get("is_market_session_date_eligible")),
                    "calendar_source": date_decision.get("calendar_source"),
                    "calendar_source_identity": date_decision.get("calendar_source_identity"),
                    "calendar_policy_identity": date_decision.get("calendar_policy_identity"),
                    "calendar_coverage_state": date_decision.get("calendar_coverage_state"),
                    "market_session_date_reason": date_decision.get("decision_reason"),
                }
            )
            base["is_qualified_acquisition_event"] = (
                bool(base.get("contract_ok"))
                and bool(eligibility.get("is_analytically_eligible"))
                and bool(market_date_ok)
            )
            base["acquisition_eligibility_state"] = eligibility.get("analytical_eligibility_state")
            if not bool(eligibility.get("is_analytically_eligible")):
                reason = eligibility.get("analytical_eligibility_reason")
            elif not market_date_ok:
                reason = date_decision.get("market_session_date_state") or "market_session_date_unresolved"
            else:
                reason = eligibility.get("analytical_eligibility_reason")
            base["acquisition_eligibility_reason"] = reason
            base["qualified_source_scope"] = eligibility.get("qualified_source_scope")
            rows.append(base)
    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .sort_values(["trade_date", "captured_time", "relative_path"], na_position="last")
        .reset_index(drop=True)
    )


def _safe_first_row(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    row = df.iloc[0].to_dict()
    for column in (CONTRACT_ID_COLUMN, CONTRACT_FINGERPRINT_COLUMN, CONTRACT_RESOLUTION_COLUMN):
        if column not in row:
            row[column] = UNKNOWN
    return row


def build_acquisition_frame(
    trade_dates: Iterable[str],
    policy: dict | None = None,
    cell_minutes: int = DEFAULT_ACQUISITION_CELL_MINUTES,
) -> pd.DataFrame:
    policy = policy or get_default_collection_policy()
    minutes = max(1, int(cell_minutes or DEFAULT_ACQUISITION_CELL_MINUTES))
    sessions = list(policy.get("sessions") or [])
    timezone = str(policy.get("timezone") or "Asia/Shanghai")
    dates = sorted({str(item) for item in trade_dates if str(item or "").strip()})
    frame_id = build_acquisition_frame_id(policy, minutes)
    rows: list[dict] = []
    for trade_date in dates:
        for session in sessions:
            start = parse_policy_time(session.get("start"))
            end = parse_policy_time(session.get("end"))
            start_seconds = _time_to_seconds(start)
            end_seconds = _time_to_seconds(end)
            if end_seconds <= start_seconds:
                continue
            cell_seconds = minutes * 60
            cell_index = 0
            cursor = start_seconds
            while cursor < end_seconds:
                cell_end_seconds = min(end_seconds, cursor + cell_seconds)
                cell_start = _seconds_to_hhmmss(cursor)
                cell_end = _seconds_to_hhmmss(cell_end_seconds)
                cell_id = _stable_id(
                    {
                        "frame_id": frame_id,
                        "trade_date": trade_date,
                        "session_name": session.get("name"),
                        "cell_index": cell_index,
                        "cell_start": cell_start,
                        "cell_end": cell_end,
                    },
                    length=16,
                )
                rows.append(
                    {
                        "acquisition_frame_id": frame_id,
                        "trade_date": trade_date,
                        "session_name": session.get("name"),
                        "session_label": session.get("label") or session.get("name"),
                        "session_start": session.get("start"),
                        "session_end": session.get("end"),
                        "cell_id": cell_id,
                        "cell_start": cell_start,
                        "cell_end": cell_end,
                        "cell_index": int(cell_index),
                        "timezone": timezone,
                        "cell_minutes": int(minutes),
                        "boundary_convention": FRAME_BOUNDARY_CONVENTION,
                    }
                )
                cell_index += 1
                cursor = cell_end_seconds
    return pd.DataFrame(rows)


def _seconds_to_hhmmss(seconds: int) -> str:
    seconds = max(0, min(int(seconds), 24 * 3600))
    hour = seconds // 3600
    minute = (seconds % 3600) // 60
    second = seconds % 60
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def build_acquisition_frame_id(policy: dict | None = None, cell_minutes: int = DEFAULT_ACQUISITION_CELL_MINUTES) -> str:
    policy = policy or get_default_collection_policy()
    payload = {
        "timezone": policy.get("timezone"),
        "cell_minutes": max(1, int(cell_minutes or DEFAULT_ACQUISITION_CELL_MINUTES)),
        "sessions": [
            {
                "name": item.get("name"),
                "start": item.get("start"),
                "end": item.get("end"),
            }
            for item in policy.get("sessions", [])
        ],
        "boundary_convention": FRAME_BOUNDARY_CONVENTION,
    }
    return _stable_id(payload, length=16)


def assign_capture_events_to_acquisition_cells(
    events_df: pd.DataFrame,
    frame_df: pd.DataFrame,
) -> pd.DataFrame:
    if events_df is None or events_df.empty:
        return pd.DataFrame() if events_df is None else events_df.copy()
    work = events_df.copy()
    if frame_df is None:
        frame_df = pd.DataFrame()
    frame_by_date = {
        str(date): group.copy()
        for date, group in frame_df.groupby(frame_df["trade_date"].astype(str), sort=False)
    } if frame_df is not None and not frame_df.empty and "trade_date" in frame_df.columns else {}

    assignment_rows: list[dict] = []
    for _, row in work.iterrows():
        captured_time = row.get("captured_time")
        parsed = _parse_time(captured_time)
        if captured_time is None or str(captured_time).strip() == "":
            assignment_rows.append(_assignment_payload(ASSIGNMENT_MISSING_TIME))
            continue
        if parsed is None:
            assignment_rows.append(_assignment_payload(ASSIGNMENT_INVALID_TIME))
            continue
        date = str(row.get("trade_date") or "")
        source_mode = str(row.get("source_mode") or "").upper()
        if source_mode == "REAL" and row.get("market_session_date_state") != STATE_ELIGIBLE:
            state = str(row.get("market_session_date_state") or STATE_UNVERIFIED)
            if state == STATE_INELIGIBLE:
                assignment_rows.append(_assignment_payload(ASSIGNMENT_DATE_INELIGIBLE))
            else:
                assignment_rows.append(_assignment_payload(ASSIGNMENT_CALENDAR_UNVERIFIED))
            continue
        cells = frame_by_date.get(date, pd.DataFrame())
        if cells.empty:
            assignment_rows.append(_assignment_payload(ASSIGNMENT_OUTSIDE))
            continue
        seconds = _time_to_seconds(parsed)
        matched = None
        for _, cell in cells.iterrows():
            start = _parse_time(cell.get("cell_start"))
            end = _parse_time(cell.get("cell_end"))
            session_end = _parse_time(cell.get("session_end"))
            if start is None or end is None:
                continue
            start_s = _time_to_seconds(start)
            end_s = _time_to_seconds(end)
            final_endpoint = session_end is not None and seconds == _time_to_seconds(session_end) and end_s == _time_to_seconds(session_end)
            if start_s <= seconds < end_s or final_endpoint:
                matched = cell
                break
        if matched is None:
            assignment_rows.append(_assignment_payload(ASSIGNMENT_OUTSIDE))
        else:
            assignment_rows.append(
                _assignment_payload(
                    ASSIGNMENT_ASSIGNED,
                    acquisition_frame_id=matched.get("acquisition_frame_id"),
                    acquisition_cell_id=matched.get("cell_id"),
                    acquisition_session_name=matched.get("session_name"),
                    acquisition_cell_start=matched.get("cell_start"),
                    acquisition_cell_end=matched.get("cell_end"),
                    acquisition_cell_index=matched.get("cell_index"),
                )
            )
    assignment = pd.DataFrame(assignment_rows, index=work.index)
    for column in assignment.columns:
        work[column] = assignment[column]
    return work


def _assignment_payload(state: str, **kwargs) -> dict:
    payload = {
        "acquisition_assignment_state": state,
        "acquisition_frame_id": None,
        "acquisition_cell_id": None,
        "acquisition_session_name": None,
        "acquisition_cell_start": None,
        "acquisition_cell_end": None,
        "acquisition_cell_index": None,
    }
    payload.update(kwargs)
    return payload


def classify_marginal_coverage_contribution(assigned_events_df: pd.DataFrame) -> pd.DataFrame:
    if assigned_events_df is None or assigned_events_df.empty:
        return pd.DataFrame() if assigned_events_df is None else assigned_events_df.copy()
    work = assigned_events_df.copy()
    work["_time_sort"] = work["captured_time"].fillna("").astype(str) if "captured_time" in work.columns else ""
    work = work.sort_values(["trade_date", "_time_sort", "capture_event_id"], na_position="last").reset_index(drop=True)
    seen_cells: set[str] = set()
    states: list[str] = []
    for _, row in work.iterrows():
        if not bool(row.get("is_qualified_acquisition_event")):
            states.append(CONTRIBUTION_EXCLUDED)
            continue
        if row.get("acquisition_assignment_state") != ASSIGNMENT_ASSIGNED or not row.get("acquisition_cell_id"):
            states.append(CONTRIBUTION_OUTSIDE)
            continue
        cell_key = f"{row.get('trade_date')}::{row.get('acquisition_cell_id')}"
        if cell_key in seen_cells:
            states.append(CONTRIBUTION_ADDITIONAL)
        else:
            seen_cells.add(cell_key)
            states.append(CONTRIBUTION_NEW_CELL)
    work["marginal_coverage_contribution"] = states
    return work.drop(columns=["_time_sort"], errors="ignore")


def build_acquisition_coverage_audit(
    events_df: pd.DataFrame,
    frame_df: pd.DataFrame,
) -> dict:
    events = classify_marginal_coverage_contribution(
        assign_capture_events_to_acquisition_cells(events_df, frame_df)
    )
    total = int(len(events)) if events is not None else 0
    if events is None or events.empty:
        qualified = pd.DataFrame()
    else:
        qualified = events[events["is_qualified_acquisition_event"].fillna(False).astype(bool)].copy()
    assigned_qualified = (
        qualified[qualified["acquisition_assignment_state"].astype(str).eq(ASSIGNMENT_ASSIGNED)].copy()
        if not qualified.empty and "acquisition_assignment_state" in qualified.columns
        else pd.DataFrame()
    )
    target_cells = int(len(frame_df)) if frame_df is not None else 0
    covered_cell_keys = set()
    if not assigned_qualified.empty:
        covered_cell_keys = set(
            (
                assigned_qualified["trade_date"].astype(str)
                + "::"
                + assigned_qualified["acquisition_cell_id"].astype(str)
            ).tolist()
        )
    covered_cells = len(covered_cell_keys)
    missing_cells = max(0, target_cells - covered_cells)
    contribution_counts = _counts(events, "marginal_coverage_contribution")
    assignment_counts = _counts(events, "acquisition_assignment_state")
    resolution_counts = _counts(events, CONTRACT_RESOLUTION_COLUMN)
    exclusion_counts = _counts(
        events[~events["is_qualified_acquisition_event"].fillna(False).astype(bool)]
        if events is not None and not events.empty and "is_qualified_acquisition_event" in events.columns
        else pd.DataFrame(),
        "acquisition_eligibility_reason",
    )
    captures_per_cell = {}
    if not assigned_qualified.empty:
        captures_per_cell = (
            assigned_qualified.groupby(["trade_date", "acquisition_session_name", "acquisition_cell_id"]).size().astype(int).to_dict()
        )
    multi_capture_cell_count = int(sum(1 for value in captures_per_cell.values() if int(value) > 1))
    return {
        "input_capture_event_count": total,
        "qualified_capture_event_count": int(len(qualified)),
        "excluded_capture_event_count": max(0, total - int(len(qualified))),
        "represented_trade_date_count": int(events["trade_date"].dropna().astype(str).nunique()) if events is not None and not events.empty and "trade_date" in events.columns else 0,
        "represented_trade_dates": sorted(events["trade_date"].dropna().astype(str).unique().tolist()) if events is not None and not events.empty and "trade_date" in events.columns else [],
        "target_acquisition_cell_count": target_cells,
        "covered_acquisition_cell_count": int(covered_cells),
        "missing_acquisition_cell_count": int(missing_cells),
        "qualified_acquisition_cell_coverage_share": round(covered_cells / target_cells, 4) if target_cells else 0.0,
        "coverage_numerator": int(covered_cells),
        "coverage_denominator": int(target_cells),
        "multi_capture_cell_count": multi_capture_cell_count,
        "off_frame_capture_count": int(assignment_counts.get(ASSIGNMENT_OUTSIDE, 0)),
        "assignment_state_counts": assignment_counts,
        "marginal_contribution_counts": contribution_counts,
        "provider_contract_resolution_counts": resolution_counts,
        "excluded_reason_counts": exclusion_counts,
        "covered_cells_by_date": _covered_cells_by_date(assigned_qualified),
        "missing_cells_by_date": _missing_cells_by_date(frame_df, assigned_qualified),
        "covered_cells_by_session": _covered_cells_by_session(assigned_qualified),
        "missing_cells_by_session": _missing_cells_by_session(frame_df, assigned_qualified),
        "capture_count_per_covered_cell": {str(k): int(v) for k, v in captures_per_cell.items()},
        "coverage_share_semantics": "observed covered cells / predeclared target cells; this is not a score.",
        "events_df": events,
    }


def _counts(df: pd.DataFrame | None, column: str) -> dict[str, int]:
    if df is None or df.empty or column not in df.columns:
        return {}
    return {str(k): int(v) for k, v in df[column].fillna("unknown").astype(str).value_counts().to_dict().items()}


def _covered_cells_by_date(assigned_qualified: pd.DataFrame) -> dict[str, int]:
    if assigned_qualified is None or assigned_qualified.empty:
        return {}
    grouped = assigned_qualified.dropna(subset=["acquisition_cell_id"]).groupby("trade_date")["acquisition_cell_id"].nunique()
    return {str(k): int(v) for k, v in grouped.to_dict().items()}


def _target_cells_by_date(frame_df: pd.DataFrame) -> dict[str, int]:
    if frame_df is None or frame_df.empty:
        return {}
    return {str(k): int(v) for k, v in frame_df.groupby("trade_date")["cell_id"].nunique().to_dict().items()}


def _missing_cells_by_date(frame_df: pd.DataFrame, assigned_qualified: pd.DataFrame) -> dict[str, int]:
    target = _target_cells_by_date(frame_df)
    covered = _covered_cells_by_date(assigned_qualified)
    return {date: max(0, int(count) - int(covered.get(date, 0))) for date, count in target.items()}


def _covered_cells_by_session(assigned_qualified: pd.DataFrame) -> dict[str, int]:
    if assigned_qualified is None or assigned_qualified.empty:
        return {}
    grouped = assigned_qualified.dropna(subset=["acquisition_cell_id"]).groupby("acquisition_session_name")["acquisition_cell_id"].nunique()
    return {str(k): int(v) for k, v in grouped.to_dict().items()}


def _missing_cells_by_session(frame_df: pd.DataFrame, assigned_qualified: pd.DataFrame) -> dict[str, int]:
    if frame_df is None or frame_df.empty:
        return {}
    target = {str(k): int(v) for k, v in frame_df.groupby("session_name")["cell_id"].nunique().to_dict().items()}
    covered = _covered_cells_by_session(assigned_qualified)
    return {session: max(0, int(count) - int(covered.get(session, 0))) for session, count in target.items()}


def build_evidence_accumulation_report(
    source_mode: str = "SAMPLE",
    data_dir: str | Path | None = None,
    cell_minutes: int = DEFAULT_ACQUISITION_CELL_MINUTES,
    trade_date: str | None = None,
    market_session_policy: dict | None = None,
) -> dict:
    source = _normalize_source(source_mode)
    directory = _source_data_dir(source, str(data_dir) if data_dir is not None else None)
    date_policy = market_session_policy or get_default_market_session_policy()
    events = build_physical_capture_event_inventory(directory, source_mode=source, market_session_policy=date_policy)
    if trade_date and not events.empty and "trade_date" in events.columns:
        events = events[events["trade_date"].astype(str).eq(str(trade_date))].copy()
    if source == "REAL" and not events.empty and "market_session_date_state" in events.columns:
        frame_events = events[events["market_session_date_state"].astype(str).eq(STATE_ELIGIBLE)].copy()
    else:
        frame_events = events
    trade_dates = frame_events["trade_date"].dropna().astype(str).unique().tolist() if not frame_events.empty and "trade_date" in frame_events.columns else []
    frame = build_acquisition_frame(trade_dates, cell_minutes=cell_minutes)
    audit = build_acquisition_coverage_audit(events, frame)
    events_with_contrib = audit.pop("events_df", pd.DataFrame())
    warning_list = []
    if source == "REAL" and audit.get("qualified_capture_event_count", 0) == 0 and audit.get("input_capture_event_count", 0) > 0:
        warning_list.append("REAL captures are readable but currently do not enter qualified acquisition coverage unless provider-contract provenance and market-session date eligibility are both satisfied.")
    if source == "SAMPLE":
        warning_list.append("SAMPLE acquisition coverage is synthetic demo evidence only and does not represent real market history.")
    date_state_counts = _counts(events, "market_session_date_state")
    eligible_frame_dates = sorted(frame["trade_date"].dropna().astype(str).unique().tolist()) if frame is not None and not frame.empty else []
    return {
        "source_mode": source,
        "data_dir": directory,
        "network_used": False,
        "market_session_date_policy": {
            "calendar_source": date_policy.get("calendar_source"),
            "calendar_source_identity": date_policy.get("calendar_source_identity"),
            "coverage_start": date_policy.get("coverage_start"),
            "coverage_end": date_policy.get("coverage_end"),
            "coverage_semantics": date_policy.get("coverage_semantics"),
            "network_used": False,
        },
        "market_session_date_state_counts": date_state_counts,
        "eligible_acquisition_frame_dates": eligible_frame_dates,
        "calendar_unverified_capture_count": int(date_state_counts.get(STATE_UNVERIFIED, 0)),
        "market_session_date_ineligible_capture_count": int(date_state_counts.get(STATE_INELIGIBLE, 0)),
        "acquisition_frame_id": build_acquisition_frame_id(cell_minutes=cell_minutes),
        "acquisition_cell_minutes": max(1, int(cell_minutes or DEFAULT_ACQUISITION_CELL_MINUTES)),
        "configured_sessions": [
            {
                "name": item.get("name"),
                "label": item.get("label"),
                "start": item.get("start"),
                "end": item.get("end"),
            }
            for item in get_default_collection_policy().get("sessions", [])
        ],
        "boundary_convention": FRAME_BOUNDARY_CONVENTION,
        "physical_capture_event_count": audit.get("input_capture_event_count", 0),
        "qualified_capture_event_count": audit.get("qualified_capture_event_count", 0),
        "excluded_capture_event_count": audit.get("excluded_capture_event_count", 0),
        "represented_dates": audit.get("represented_trade_dates", []),
        "represented_trade_date_count": audit.get("represented_trade_date_count", 0),
        "target_acquisition_cell_count": audit.get("target_acquisition_cell_count", 0),
        "covered_acquisition_cell_count": audit.get("covered_acquisition_cell_count", 0),
        "missing_acquisition_cell_count": audit.get("missing_acquisition_cell_count", 0),
        "covered_cells_by_date": audit.get("covered_cells_by_date", {}),
        "missing_cells_by_date": audit.get("missing_cells_by_date", {}),
        "covered_cells_by_session": audit.get("covered_cells_by_session", {}),
        "missing_cells_by_session": audit.get("missing_cells_by_session", {}),
        "capture_count_per_covered_cell": audit.get("capture_count_per_covered_cell", {}),
        "multi_capture_cell_count": audit.get("multi_capture_cell_count", 0),
        "off_frame_capture_count": audit.get("off_frame_capture_count", 0),
        "coverage_numerator": audit.get("coverage_numerator", 0),
        "coverage_denominator": audit.get("coverage_denominator", 0),
        "qualified_acquisition_cell_coverage_share": audit.get("qualified_acquisition_cell_coverage_share", 0.0),
        "provider_contract_resolution_counts": audit.get("provider_contract_resolution_counts", {}),
        "assignment_state_counts": audit.get("assignment_state_counts", {}),
        "marginal_contribution_counts": audit.get("marginal_contribution_counts", {}),
        "excluded_reason_counts": audit.get("excluded_reason_counts", {}),
        "events_preview": _events_preview(events_with_contrib),
        "coverage_share_semantics": audit.get("coverage_share_semantics"),
        "warnings": warning_list,
        "errors": [],
    }


def _events_preview(events_df: pd.DataFrame, limit: int = 20) -> list[dict]:
    if events_df is None or events_df.empty:
        return []
    columns = [
        "capture_event_id",
        "trade_date",
        "captured_time",
        "source_mode",
        "market_session_date_state",
        CONTRACT_RESOLUTION_COLUMN,
        "is_qualified_acquisition_event",
        "acquisition_assignment_state",
        "acquisition_cell_id",
        "acquisition_session_name",
        "marginal_coverage_contribution",
    ]
    present = [column for column in columns if column in events_df.columns]
    return events_df[present].head(limit).to_dict(orient="records")


def summarize_evidence_accumulation(report: dict) -> str:
    report = report or {}
    return (
        f"{report.get('source_mode', '--')} acquisition audit: "
        f"{int(report.get('qualified_capture_event_count', 0) or 0)} qualified captures cover "
        f"{int(report.get('coverage_numerator', 0) or 0)} / {int(report.get('coverage_denominator', 0) or 0)} "
        "predeclared acquisition cells. Capture count and cell coverage are reported separately."
    )


def validate_evidence_accumulation_text(text: str) -> list[str]:
    return sorted({word for word in FORBIDDEN_EVIDENCE_ACCUMULATION_WORDS if word in str(text or "")})
