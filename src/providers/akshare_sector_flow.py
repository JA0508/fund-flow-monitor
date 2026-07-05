from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import pandas as pd
import requests

from src.config import DATA_SOURCE, TIMEZONE
from src.utils import safe_to_float


PROVIDER_NAME = "AKShare / Eastmoney"
API_NAME = "stock_sector_fund_flow_rank"
DEFAULT_INDICATOR = "今日"
DEFAULT_SECTOR_TYPE = "行业资金流"
RETRYABLE_ERROR_CATEGORIES = {"network_error", "timeout_error"}

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "rank_value": ("序号", "排名", "排行", "rank"),
    "sector_code": ("板块代码", "代码", "行业代码", "概念代码", "f12"),
    "sector_name": ("名称", "板块名称", "行业名称", "概念名称", "f14"),
    "change_pct": ("今日涨跌幅", "涨跌幅", "涨跌幅%", "涨跌幅(%)", "f3"),
    "main_net_inflow_yuan": ("今日主力净流入-净额", "主力净流入-净额", "主力净流入净额", "f62"),
    "main_net_ratio": ("今日主力净流入-净占比", "主力净流入-净占比", "主力净流入净占比", "f184"),
    "super_large_net_inflow_yuan": ("今日超大单净流入-净额", "超大单净流入-净额", "超大单净流入净额", "f66"),
    "large_net_inflow_yuan": ("今日大单净流入-净额", "大单净流入-净额", "大单净流入净额", "f72"),
    "medium_net_inflow_yuan": ("今日中单净流入-净额", "中单净流入-净额", "中单净流入净额", "f78"),
    "small_net_inflow_yuan": ("今日小单净流入-净额", "小单净流入-净额", "小单净流入净额", "f84"),
    "leading_stock": ("今日主力净流入最大股", "主力净流入最大股", "领涨股", "龙头股", "f204"),
    "leading_stock_code": ("今日主力净流入最大股代码", "主力净流入最大股代码", "f205"),
}

REQUIRED_PROVIDER_FIELDS = ("sector_name", "main_net_inflow_yuan")
NUMERIC_FIELDS = (
    "rank_value",
    "change_pct",
    "main_net_inflow_yuan",
    "main_net_ratio",
    "super_large_net_inflow_yuan",
    "large_net_inflow_yuan",
    "medium_net_inflow_yuan",
    "small_net_inflow_yuan",
)

OUTPUT_COLUMNS = [
    "trade_date",
    "captured_at",
    "captured_time",
    "fetched_at",
    "sector_type",
    "rank_value",
    "sector_code",
    "sector_name",
    "change_pct",
    "main_net_inflow_yuan",
    "main_net_inflow_billion",
    "main_net_ratio",
    "super_large_net_inflow_yuan",
    "large_net_inflow_yuan",
    "medium_net_inflow_yuan",
    "small_net_inflow_yuan",
    "leading_stock",
    "source",
    "provider",
    "api_name",
    "data_mode",
]


class ProviderBoundaryError(RuntimeError):
    """Raised when the AKShare provider boundary cannot produce a valid snapshot."""

    def __init__(self, message: str, category: str, diagnostic: dict | None = None, original: Exception | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.diagnostic = diagnostic or {}
        self.original = original


@dataclass
class ProviderFetchResult:
    raw_df: pd.DataFrame | None
    normalized_df: pd.DataFrame | None
    diagnostic: dict


def _now_iso() -> str:
    return pd.Timestamp.now(tz=TIMEZONE).isoformat()


def _normalize_column_name(column: object) -> str:
    return str(column).strip().replace(" ", "").replace("_", "").replace("-", "").lower()


def build_schema_fingerprint(columns: Iterable[object]) -> str:
    normalized = [_normalize_column_name(column) for column in columns]
    payload = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _dtype_summary(df: pd.DataFrame | None) -> dict[str, str]:
    if df is None:
        return {}
    return {str(column): str(dtype) for column, dtype in df.dtypes.items()}


def build_provider_diagnostic(
    *,
    sector_type: str,
    indicator: str,
    response: object | None = None,
    normalization_status: str = "not_run",
    contract_status: str | None = None,
    error_category: str | None = None,
    error_type: str | None = None,
    message: str | None = None,
    retry_count: int = 0,
) -> dict:
    is_dataframe = isinstance(response, pd.DataFrame)
    columns = [str(column) for column in response.columns] if is_dataframe else []
    return {
        "provider": PROVIDER_NAME,
        "api_name": API_NAME,
        "sector_type": sector_type,
        "indicator": indicator,
        "fetch_timestamp": _now_iso(),
        "response_type": type(response).__name__ if response is not None else None,
        "row_count": int(len(response)) if is_dataframe else 0,
        "column_names": columns,
        "normalized_column_names": [_normalize_column_name(column) for column in columns],
        "dtype_summary": _dtype_summary(response if is_dataframe else None),
        "schema_fingerprint": build_schema_fingerprint(columns) if columns else None,
        "normalization_status": normalization_status,
        "contract_status": contract_status,
        "error_category": error_category,
        "error_type": error_type,
        "message": message,
        "retry_count": int(retry_count or 0),
    }


def classify_provider_exception(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if isinstance(exc, (requests.exceptions.Timeout, TimeoutError)) or "timeout" in name or "timed out" in message:
        return "timeout_error"
    if isinstance(exc, requests.exceptions.RequestException) or "connection" in message or "network" in message:
        return "network_error"
    if "jsondecodeerror" in name or "expecting value" in message or "json" in name:
        return "provider_parse_error"
    if isinstance(exc, (KeyError, ValueError, TypeError, IndexError)):
        return "provider_parse_error"
    return "provider_error"


def _raise_boundary_error(
    message: str,
    category: str,
    *,
    sector_type: str,
    indicator: str,
    response: object | None = None,
    normalization_status: str = "failed",
    original: Exception | None = None,
    retry_count: int = 0,
) -> None:
    diagnostic = build_provider_diagnostic(
        sector_type=sector_type,
        indicator=indicator,
        response=response,
        normalization_status=normalization_status,
        error_category=category,
        error_type=type(original).__name__ if original is not None else category,
        message=message,
        retry_count=retry_count,
    )
    raise ProviderBoundaryError(message, category=category, diagnostic=diagnostic, original=original)


def _build_column_index(columns: Iterable[object]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for column in columns:
        text = str(column)
        index.setdefault(_normalize_column_name(text), []).append(text)
    return index


def resolve_provider_columns(raw_df: pd.DataFrame) -> dict[str, str | None]:
    column_index = _build_column_index(raw_df.columns)
    resolved: dict[str, str | None] = {}
    ambiguities: list[str] = []
    for target, aliases in FIELD_ALIASES.items():
        matches: list[str] = []
        for alias in aliases:
            matches.extend(column_index.get(_normalize_column_name(alias), []))
        unique_matches = list(dict.fromkeys(matches))
        if len(unique_matches) > 1:
            ambiguities.append(f"{target}: {unique_matches}")
            resolved[target] = None
        elif unique_matches:
            resolved[target] = unique_matches[0]
        else:
            resolved[target] = None
    if ambiguities:
        raise ProviderBoundaryError(
            "AKShare 返回列存在重复候选映射，已拒绝自动选择。",
            category="schema_drift",
            diagnostic={
                "provider": PROVIDER_NAME,
                "api_name": API_NAME,
                "column_names": [str(column) for column in raw_df.columns],
                "schema_fingerprint": build_schema_fingerprint(raw_df.columns),
                "normalization_status": "schema_drift",
                "error_category": "schema_drift",
                "message": "; ".join(ambiguities),
            },
        )
    return resolved


def _series_or_none(raw_df: pd.DataFrame, column: str | None) -> pd.Series:
    if column is None:
        return pd.Series([None] * len(raw_df), index=raw_df.index)
    return raw_df[column]


def _normalize_timestamp(captured_at: datetime | None) -> pd.Timestamp:
    if captured_at is None:
        return pd.Timestamp.now(tz=TIMEZONE)
    ts = pd.Timestamp(captured_at)
    if ts.tzinfo is None:
        return ts.tz_localize(TIMEZONE)
    return ts.tz_convert(TIMEZONE)


def normalize_provider_dataframe(
    raw_df: pd.DataFrame | None,
    *,
    sector_type: str,
    indicator: str = DEFAULT_INDICATOR,
    captured_at: datetime | None = None,
    strict_schema: bool = True,
) -> ProviderFetchResult:
    if raw_df is None:
        _raise_boundary_error(
            "AKShare 返回 None，无法规范化。",
            "empty_response",
            sector_type=sector_type,
            indicator=indicator,
            response=None,
            normalization_status="not_run",
        )
    if not isinstance(raw_df, pd.DataFrame):
        _raise_boundary_error(
            "AKShare 返回结果不是 DataFrame。",
            "provider_error",
            sector_type=sector_type,
            indicator=indicator,
            response=raw_df,
            normalization_status="not_run",
        )
    if raw_df.empty:
        _raise_boundary_error(
            "AKShare 返回空 DataFrame。",
            "empty_response",
            sector_type=sector_type,
            indicator=indicator,
            response=raw_df,
            normalization_status="not_run",
        )
    try:
        resolved = resolve_provider_columns(raw_df)
    except ProviderBoundaryError as exc:
        diagnostic = dict(exc.diagnostic)
        diagnostic.update(
            build_provider_diagnostic(
                sector_type=sector_type,
                indicator=indicator,
                response=raw_df,
                normalization_status="schema_drift",
                error_category="schema_drift",
                error_type="ProviderBoundaryError",
                message=str(exc),
            )
        )
        raise ProviderBoundaryError(str(exc), category="schema_drift", diagnostic=diagnostic, original=exc) from exc

    missing_required = [field for field in REQUIRED_PROVIDER_FIELDS if not resolved.get(field)]
    if missing_required and strict_schema:
        _raise_boundary_error(
            f"AKShare 返回 schema 缺少必要列映射：{', '.join(missing_required)}。",
            "schema_drift",
            sector_type=sector_type,
            indicator=indicator,
            response=raw_df,
            normalization_status="schema_drift",
        )

    captured_ts = _normalize_timestamp(captured_at)
    normalized = pd.DataFrame(index=raw_df.index)
    for target in FIELD_ALIASES:
        normalized[target] = _series_or_none(raw_df, resolved.get(target))

    try:
        for column in NUMERIC_FIELDS:
            normalized[column] = normalized[column].map(safe_to_float)
        normalized["sector_code"] = normalized["sector_code"].fillna("").astype(str)
        normalized["sector_name"] = normalized["sector_name"].astype("string").str.strip()
        normalized["leading_stock"] = normalized["leading_stock"].astype("string").str.strip()

        code_text = normalized["leading_stock_code"].fillna("").astype(str).str.strip()
        has_code = code_text.ne("")
        normalized.loc[has_code, "leading_stock"] = (
            normalized.loc[has_code, "leading_stock"].fillna("")
            + " "
            + code_text.loc[has_code]
        ).str.strip()

        normalized["main_net_inflow_billion"] = normalized["main_net_inflow_yuan"] / 100_000_000.0
        normalized["captured_at"] = captured_ts
        normalized["captured_time"] = captured_ts.strftime("%H:%M:%S")
        normalized["trade_date"] = captured_ts.strftime("%Y-%m-%d")
        normalized["fetched_at"] = captured_ts.isoformat()
        normalized["sector_type"] = sector_type
        normalized["source"] = DATA_SOURCE
        normalized["provider"] = PROVIDER_NAME
        normalized["api_name"] = API_NAME
        normalized["data_mode"] = "REAL"
        normalized = normalized.drop(columns=["leading_stock_code"], errors="ignore")
        normalized = normalized[
            normalized["sector_name"].notna()
            & normalized["sector_name"].ne("")
            & normalized["main_net_inflow_yuan"].map(lambda value: not pd.isna(value))
        ]
    except Exception as exc:
        _raise_boundary_error(
            f"AKShare 数据规范化失败：{exc}",
            "normalization_error",
            sector_type=sector_type,
            indicator=indicator,
            response=raw_df,
            normalization_status="failed",
            original=exc,
        )

    if normalized.empty:
        _raise_boundary_error(
            "AKShare 数据规范化后没有可用记录。",
            "normalization_error",
            sector_type=sector_type,
            indicator=indicator,
            response=raw_df,
            normalization_status="empty_after_normalization",
        )

    diagnostic = build_provider_diagnostic(
        sector_type=sector_type,
        indicator=indicator,
        response=raw_df,
        normalization_status="success",
        message="AKShare provider schema 已按显式映射规范化。",
    )
    diagnostic["resolved_columns"] = {key: value for key, value in resolved.items() if value}
    diagnostic["normalized_row_count"] = int(len(normalized))
    return ProviderFetchResult(
        raw_df=raw_df,
        normalized_df=normalized[OUTPUT_COLUMNS].reset_index(drop=True),
        diagnostic=diagnostic,
    )


def fetch_raw_sector_flow(
    *,
    sector_type: str = DEFAULT_SECTOR_TYPE,
    indicator: str = DEFAULT_INDICATOR,
    attempts: int = 1,
    retry_backoff_seconds: float = 0.3,
) -> ProviderFetchResult:
    attempts = max(1, min(int(attempts or 1), 3))
    last_error: Exception | None = None
    retry_count = 0
    for attempt in range(1, attempts + 1):
        try:
            import akshare as ak
        except ImportError as exc:
            _raise_boundary_error(
                "AKShare 未安装，请先运行 pip install -r requirements.txt。",
                "provider_error",
                sector_type=sector_type,
                indicator=indicator,
                original=exc,
                retry_count=retry_count,
            )
        try:
            if not hasattr(ak, API_NAME):
                raise AttributeError(f"当前 AKShare 版本缺少 {API_NAME} 接口")
            df = ak.stock_sector_fund_flow_rank(indicator=indicator, sector_type=sector_type)
            if not isinstance(df, pd.DataFrame):
                _raise_boundary_error(
                    "AKShare 返回结果不是 DataFrame。",
                    "provider_error",
                    sector_type=sector_type,
                    indicator=indicator,
                    response=df,
                    retry_count=retry_count,
                )
            diagnostic = build_provider_diagnostic(
                sector_type=sector_type,
                indicator=indicator,
                response=df,
                normalization_status="not_run",
                message="AKShare raw fetch succeeded.",
                retry_count=retry_count,
            )
            return ProviderFetchResult(raw_df=df, normalized_df=None, diagnostic=diagnostic)
        except ProviderBoundaryError:
            raise
        except Exception as exc:
            last_error = exc
            category = classify_provider_exception(exc)
            if category in RETRYABLE_ERROR_CATEGORIES and attempt < attempts:
                retry_count += 1
                time.sleep(max(0.0, retry_backoff_seconds) * attempt)
                continue
            _raise_boundary_error(
                f"AKShare provider 调用失败：{exc}",
                category,
                sector_type=sector_type,
                indicator=indicator,
                original=exc,
                retry_count=retry_count,
            )
    _raise_boundary_error(
        f"AKShare provider 调用失败：{last_error}",
        classify_provider_exception(last_error) if last_error else "provider_error",
        sector_type=sector_type,
        indicator=indicator,
        original=last_error,
        retry_count=retry_count,
    )


def fetch_and_normalize_sector_flow(
    *,
    sector_type: str = DEFAULT_SECTOR_TYPE,
    indicator: str = DEFAULT_INDICATOR,
    captured_at: datetime | None = None,
    attempts: int = 1,
) -> ProviderFetchResult:
    raw_result = fetch_raw_sector_flow(sector_type=sector_type, indicator=indicator, attempts=attempts)
    normalized_result = normalize_provider_dataframe(
        raw_result.raw_df,
        sector_type=sector_type,
        indicator=indicator,
        captured_at=captured_at,
        strict_schema=True,
    )
    diagnostic = dict(raw_result.diagnostic)
    diagnostic.update(normalized_result.diagnostic)
    diagnostic["retry_count"] = raw_result.diagnostic.get("retry_count", 0)
    return ProviderFetchResult(
        raw_df=raw_result.raw_df,
        normalized_df=normalized_result.normalized_df,
        diagnostic=diagnostic,
    )


def validate_provider_text(text: str) -> list[str]:
    forbidden = (
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
    return [word for word in forbidden if word in text]

