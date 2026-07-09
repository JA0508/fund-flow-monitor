from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


UNKNOWN = "unknown"
PRIMARY_PROVIDER_ID = "akshare_eastmoney_sector_fund_flow_rank_today_industry"
PRIMARY_PROVIDER_CONTRACT_VERSION = "v1"

SEMANTIC_CONTRACT_FIELDS = (
    "provider_id",
    "provider_name",
    "upstream_origin",
    "api_name",
    "api_arguments",
    "metric_family",
    "metric_semantics",
    "time_semantics",
    "capture_semantics",
    "row_grain",
    "universe_semantics",
    "value_semantics",
    "unit",
    "sign_semantics",
    "timezone",
    "required_source_fields",
    "internal_contract_name",
    "normalization_path",
    "contract_version",
)

FORBIDDEN_PROVIDER_CONTRACT_WORDS = (
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


@dataclass(frozen=True)
class ProviderSemanticContract:
    provider_id: str
    provider_name: str
    upstream_origin: str = UNKNOWN
    api_name: str = UNKNOWN
    api_arguments: dict[str, Any] | None = None
    metric_family: str = UNKNOWN
    metric_semantics: str = UNKNOWN
    time_semantics: str = UNKNOWN
    capture_semantics: str = UNKNOWN
    row_grain: str = UNKNOWN
    universe_semantics: str = UNKNOWN
    value_semantics: str = UNKNOWN
    unit: str = UNKNOWN
    sign_semantics: str = UNKNOWN
    timezone: str = UNKNOWN
    required_source_fields: tuple[str, ...] = ()
    internal_contract_name: str = UNKNOWN
    normalization_path: str = UNKNOWN
    contract_version: str = "v1"
    source_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["api_arguments"] = dict(self.api_arguments or {})
        payload["required_source_fields"] = list(self.required_source_fields)
        payload["source_notes"] = list(self.source_notes)
        payload["semantic_contract_id"] = build_provider_contract_fingerprint(self)
        payload["semantic_contract_short_id"] = payload["semantic_contract_id"][:12]
        return payload


def _canonicalize(value: Any) -> Any:
    if value is None:
        return UNKNOWN
    if isinstance(value, str):
        stripped = " ".join(value.strip().split())
        return stripped or UNKNOWN
    if isinstance(value, dict):
        return {str(key): _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_canonicalize(item) for item in value]
    return value


def build_provider_contract_payload(contract: ProviderSemanticContract | dict[str, Any]) -> dict[str, Any]:
    raw = asdict(contract) if isinstance(contract, ProviderSemanticContract) else dict(contract)
    return {
        field: _canonicalize(raw.get(field, UNKNOWN))
        for field in SEMANTIC_CONTRACT_FIELDS
    }


def build_provider_contract_fingerprint(contract: ProviderSemanticContract | dict[str, Any]) -> str:
    payload = build_provider_contract_payload(contract)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_provider_contract_short_id(contract: ProviderSemanticContract | dict[str, Any]) -> str:
    return build_provider_contract_fingerprint(contract)[:12]


def render_provider_contract_human(contract: ProviderSemanticContract | dict[str, Any]) -> str:
    data = contract.to_dict() if isinstance(contract, ProviderSemanticContract) else dict(contract)
    return (
        f"{data.get('provider_id')} | {data.get('provider_name')} | "
        f"{data.get('api_name')} | {data.get('metric_semantics')} | "
        f"{data.get('time_semantics')} | {data.get('row_grain')} | "
        f"contract={build_provider_contract_short_id(data)}"
    )


def build_primary_provider_contract() -> ProviderSemanticContract:
    return ProviderSemanticContract(
        provider_id=PRIMARY_PROVIDER_ID,
        provider_name="AKShare / Eastmoney",
        upstream_origin="Eastmoney push2.eastmoney.com / data.eastmoney.com 板块资金流",
        api_name="ak.stock_sector_fund_flow_rank",
        api_arguments={"indicator": "今日", "sector_type": "行业资金流"},
        metric_family="sector_fund_flow",
        metric_semantics="Eastmoney board/sector fund-flow ranking for the selected indicator and sector_type.",
        time_semantics="今日 ranking returned by provider; project treats each fetch as an as-of-capture snapshot.",
        capture_semantics="one normalized CSV snapshot per manual capture timestamp; values are not blended across captures.",
        row_grain="one row per Eastmoney industry-sector board at capture time",
        universe_semantics="Eastmoney 行业资金流 sector universe exposed through AKShare sector_type=行业资金流.",
        value_semantics="今日主力净流入-净额 normalized to main_net_inflow_yuan and main_net_inflow_billion.",
        unit="yuan in provider response; billion yuan in normalized project column",
        sign_semantics="positive means net inflow, negative means net outflow, following provider field sign.",
        timezone="Asia/Shanghai capture timestamp assigned by project",
        required_source_fields=("名称", "今日主力净流入-净额"),
        internal_contract_name="normalized_sector_flow_snapshot_v1",
        normalization_path="src.providers.akshare_sector_flow.normalize_provider_dataframe",
        contract_version=PRIMARY_PROVIDER_CONTRACT_VERSION,
        source_notes=(
            "Provider/API semantics are inferred from installed AKShare docstring and source mapping.",
            "Cumulative/as-of-capture interpretation is a project-level analytical treatment, not an official provider guarantee.",
            "Downstream theme analytics consume normalized CSV snapshots and preserve provider lineage.",
        ),
    )


def validate_provider_contract_text(text: str) -> list[str]:
    value = str(text or "")
    return [word for word in FORBIDDEN_PROVIDER_CONTRACT_WORDS if word in value]
