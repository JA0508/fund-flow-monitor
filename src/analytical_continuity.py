from __future__ import annotations

import hashlib
import json
from typing import Iterable

import pandas as pd

from src.provider_contracts import UNKNOWN
from src.provider_registry import infer_provider_contract_id


SAMPLE_SYNTHETIC_CONTRACT_ID = "sample_synthetic_demo_contract"
UNKNOWN_PROVIDER_CONTRACT_ID = "unknown_provider_contract"

RESOLUTION_EXPLICIT_VERIFIED = "explicit_verified"
RESOLUTION_EXPLICIT_ID_ONLY = "explicit_id_only"
RESOLUTION_INFERRED = "inferred_from_provider_metadata"
RESOLUTION_SAMPLE_SYNTHETIC = "sample_synthetic"
RESOLUTION_UNKNOWN = "unknown"

CONTINUITY_SEGMENT_COLUMN = "analytical_continuity_segment_id"
CONTRACT_ID_COLUMN = "provider_contract_id"
CONTRACT_FINGERPRINT_COLUMN = "provider_contract_fingerprint"
CONTRACT_RESOLUTION_COLUMN = "provider_contract_resolution_state"

CONTINUITY_IDENTITY_COLUMNS = (
    "source_mode",
    CONTRACT_ID_COLUMN,
    CONTRACT_RESOLUTION_COLUMN,
    CONTRACT_FINGERPRINT_COLUMN,
)

FORBIDDEN_ANALYTICAL_CONTINUITY_WORDS = (
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
    "continuity score",
    "probability",
)


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text == "" or text.lower() in {"none", "nan", UNKNOWN}


def _clean(value: object, fallback: str = UNKNOWN) -> str:
    if _is_missing(value):
        return fallback
    return str(value).strip()


def _is_unknown_contract_id(value: object) -> bool:
    text = _clean(value, "").strip()
    return text == "" or text in {UNKNOWN, UNKNOWN_PROVIDER_CONTRACT_ID}


def build_continuity_segment_id(
    source_mode: object,
    provider_contract_id: object,
    resolution_state: object,
    provider_contract_fingerprint: object = UNKNOWN,
) -> str:
    payload = {
        "source_mode": _clean(source_mode, UNKNOWN).upper(),
        "provider_contract_id": _clean(provider_contract_id, UNKNOWN_PROVIDER_CONTRACT_ID),
        "provider_contract_resolution_state": _clean(resolution_state, RESOLUTION_UNKNOWN),
        "provider_contract_fingerprint": _clean(provider_contract_fingerprint, UNKNOWN),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def resolve_provider_contract_lineage(row: dict | pd.Series | None, source_mode: str | None = None) -> dict:
    data = row.to_dict() if isinstance(row, pd.Series) else dict(row or {})
    mode = _clean(source_mode or data.get("source_mode") or data.get("data_mode"), "REAL").upper()
    explicit_id = _clean(data.get(CONTRACT_ID_COLUMN), "")
    explicit_fp = _clean(data.get(CONTRACT_FINGERPRINT_COLUMN), UNKNOWN)

    if mode == "SAMPLE":
        contract_id = explicit_id if not _is_unknown_contract_id(explicit_id) else SAMPLE_SYNTHETIC_CONTRACT_ID
        resolution_state = RESOLUTION_SAMPLE_SYNTHETIC
    elif explicit_id and not _is_unknown_contract_id(explicit_id):
        contract_id = explicit_id
        resolution_state = RESOLUTION_EXPLICIT_VERIFIED if explicit_fp != UNKNOWN else RESOLUTION_EXPLICIT_ID_ONLY
    else:
        inferred = infer_provider_contract_id(
            data.get("provider"),
            data.get("api_name"),
            data.get("sector_type"),
            data.get("data_mode") or mode,
        )
        if inferred and inferred != UNKNOWN_PROVIDER_CONTRACT_ID:
            contract_id = inferred
            resolution_state = RESOLUTION_INFERRED
        else:
            contract_id = UNKNOWN_PROVIDER_CONTRACT_ID
            resolution_state = RESOLUTION_UNKNOWN

    segment_id = build_continuity_segment_id(mode, contract_id, resolution_state, explicit_fp)
    return {
        "source_mode": mode,
        CONTRACT_ID_COLUMN: contract_id,
        CONTRACT_FINGERPRINT_COLUMN: explicit_fp,
        CONTRACT_RESOLUTION_COLUMN: resolution_state,
        CONTINUITY_SEGMENT_COLUMN: segment_id,
        "provider_contract_resolution_label": {
            RESOLUTION_EXPLICIT_VERIFIED: "explicit semantic contract with fingerprint",
            RESOLUTION_EXPLICIT_ID_ONLY: "explicit contract ID without fingerprint",
            RESOLUTION_INFERRED: "contract inferred from provider metadata",
            RESOLUTION_SAMPLE_SYNTHETIC: "SAMPLE synthetic demo contract",
            RESOLUTION_UNKNOWN: "unknown provider contract",
        }.get(resolution_state, "unknown provider contract"),
    }


def attach_continuity_columns(df: pd.DataFrame | None, source_mode: str | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()
    work = df.copy()
    records = [resolve_provider_contract_lineage(row, source_mode=source_mode) for _, row in work.iterrows()]
    lineage_df = pd.DataFrame(records, index=work.index)
    for column in lineage_df.columns:
        work[column] = lineage_df[column]
    return work


def build_continuity_summary(df: pd.DataFrame | None) -> dict:
    if df is None or df.empty:
        return {
            "continuity_available": False,
            "continuity_segment_count": 0,
            "provider_contract_count": 0,
            "resolution_state_counts": {},
            "continuity_segment_observation_counts": {},
            "continuity_segment_trade_date_counts": {},
            "unknown_contract_observation_count": 0,
            "inferred_contract_observation_count": 0,
            "dominant_continuity_segment_share": 0.0,
        }
    work = attach_continuity_columns(df)
    segment_counts = work[CONTINUITY_SEGMENT_COLUMN].fillna(UNKNOWN).astype(str).value_counts().to_dict()
    dominant_share = 0.0
    total = len(work)
    if total and segment_counts:
        dominant_share = round(max(segment_counts.values()) / total, 4)
    if "trade_date" in work.columns:
        segment_dates = (
            work.groupby(CONTINUITY_SEGMENT_COLUMN)["trade_date"].nunique().astype(int).to_dict()
        )
    else:
        segment_dates = {}
    resolution_counts = work[CONTRACT_RESOLUTION_COLUMN].fillna(RESOLUTION_UNKNOWN).astype(str).value_counts().to_dict()
    return {
        "continuity_available": True,
        "continuity_segment_count": int(work[CONTINUITY_SEGMENT_COLUMN].dropna().astype(str).nunique()),
        "provider_contract_count": int(work[CONTRACT_ID_COLUMN].dropna().astype(str).nunique()),
        "provider_contract_counts": work[CONTRACT_ID_COLUMN].fillna(UNKNOWN).astype(str).value_counts().to_dict(),
        "resolution_state_counts": resolution_counts,
        "continuity_segment_observation_counts": {str(k): int(v) for k, v in segment_counts.items()},
        "continuity_segment_trade_date_counts": {str(k): int(v) for k, v in segment_dates.items()},
        "unknown_contract_observation_count": int(resolution_counts.get(RESOLUTION_UNKNOWN, 0)),
        "inferred_contract_observation_count": int(resolution_counts.get(RESOLUTION_INFERRED, 0)),
        "dominant_continuity_segment_share": dominant_share,
    }


def continuity_group_columns(existing_columns: Iterable[str], include_theme_definition: bool = True) -> list[str]:
    candidates = [
        "source_mode",
        CONTINUITY_SEGMENT_COLUMN,
        "taxonomy_fingerprint",
    ]
    if include_theme_definition:
        candidates.append("theme_definition_fingerprint")
    available = set(existing_columns)
    return [column for column in candidates if column in available]


def validate_analytical_continuity_text(text: str) -> list[str]:
    value = str(text or "")
    return [word for word in FORBIDDEN_ANALYTICAL_CONTINUITY_WORDS if word in value]
