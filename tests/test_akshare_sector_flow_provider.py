from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
import pytest
import requests

from src.providers import akshare_sector_flow as provider


def _raw_today_schema() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "名称": ["半导体", "银行"],
            "今日涨跌幅": ["1.2%", "-0.8%"],
            "今日主力净流入-净额": ["2.5亿", "-5000万"],
            "今日主力净流入-净占比": ["3.2%", "-1.1%"],
            "今日超大单净流入-净额": ["1亿", "-1000万"],
            "今日大单净流入-净额": ["5000万", "-1000万"],
            "今日中单净流入-净额": ["-2000万", "100万"],
            "今日小单净流入-净额": ["-1000万", "500万"],
            "今日主力净流入最大股": ["中芯国际", "招商银行"],
            "今日主力净流入最大股代码": ["688981", "600036"],
        }
    )


def _raw_legacy_schema() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "板块代码": ["BK001"],
            "板块名称": ["半导体"],
            "涨跌幅": [1.2],
            "主力净流入-净额": [100_000_000],
            "主力净流入-净占比": [2.5],
        }
    )


def test_schema_fingerprint_is_deterministic():
    first = provider.build_schema_fingerprint(["名称", "今日主力净流入-净额"])
    second = provider.build_schema_fingerprint(["名称", "今日主力净流入-净额"])
    assert first == second
    assert len(first) == 16


def test_known_today_schema_normalizes():
    result = provider.normalize_provider_dataframe(
        _raw_today_schema(),
        sector_type="行业资金流",
        captured_at=datetime(2026, 6, 1, 10, 0),
    )
    df = result.normalized_df
    assert df is not None
    assert df.loc[0, "sector_name"] == "半导体"
    assert df.loc[0, "main_net_inflow_billion"] == 2.5
    assert df.loc[0, "leading_stock"] == "中芯国际 688981"
    assert result.diagnostic["normalization_status"] == "success"
    assert result.diagnostic["schema_fingerprint"]


def test_legacy_schema_variant_normalizes():
    result = provider.normalize_provider_dataframe(
        _raw_legacy_schema(),
        sector_type="行业资金流",
        captured_at=datetime(2026, 6, 1, 10, 0),
    )
    assert result.normalized_df is not None
    assert result.normalized_df.loc[0, "sector_name"] == "半导体"
    assert result.normalized_df.loc[0, "main_net_inflow_billion"] == 1.0


def test_unknown_schema_fails_as_schema_drift():
    with pytest.raises(provider.ProviderBoundaryError) as excinfo:
        provider.normalize_provider_dataframe(
            pd.DataFrame({"unknown_name": ["半导体"], "unknown_amount": [1]}),
            sector_type="行业资金流",
        )
    assert excinfo.value.category == "schema_drift"
    assert excinfo.value.diagnostic["schema_fingerprint"]


def test_missing_required_amount_column_fails_as_schema_drift():
    with pytest.raises(provider.ProviderBoundaryError) as excinfo:
        provider.normalize_provider_dataframe(pd.DataFrame({"名称": ["半导体"]}), sector_type="行业资金流")
    assert excinfo.value.category == "schema_drift"


def test_ambiguous_column_mapping_fails_clearly():
    raw = pd.DataFrame(
        {
            "名称": ["半导体"],
            " 名称 ": ["芯片"],
            "今日主力净流入-净额": [1],
        }
    )
    with pytest.raises(provider.ProviderBoundaryError) as excinfo:
        provider.normalize_provider_dataframe(raw, sector_type="行业资金流")
    assert excinfo.value.category == "schema_drift"
    assert "重复候选映射" in str(excinfo.value)


def test_empty_provider_dataframe_category():
    with pytest.raises(provider.ProviderBoundaryError) as excinfo:
        provider.normalize_provider_dataframe(pd.DataFrame(), sector_type="行业资金流")
    assert excinfo.value.category == "empty_response"


def test_normalization_error_when_amounts_cannot_be_used():
    raw = pd.DataFrame({"名称": ["半导体"], "今日主力净流入-净额": ["--"]})
    with pytest.raises(provider.ProviderBoundaryError) as excinfo:
        provider.normalize_provider_dataframe(raw, sector_type="行业资金流")
    assert excinfo.value.category == "normalization_error"


def test_classify_network_timeout_and_provider_parse_errors():
    assert provider.classify_provider_exception(requests.exceptions.ConnectionError("network down")) == "network_error"
    assert provider.classify_provider_exception(requests.exceptions.Timeout("timeout")) == "timeout_error"
    assert provider.classify_provider_exception(json.JSONDecodeError("Expecting value", "", 0)) == "provider_parse_error"


def test_provider_error_message_redacts_request_query():
    text = provider.sanitize_provider_error_message("failed with url: /api/qt/clist/get?token=secret&fields=f62")
    assert "/api/qt/clist/get" not in text
    assert "secret" not in text
    assert "<request_url_redacted>" in text


def test_retryable_failure_followed_by_success(monkeypatch):
    calls = {"count": 0}

    class FakeAk:
        __version__ = "test"

        @staticmethod
        def stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流"):
            calls["count"] += 1
            if calls["count"] == 1:
                raise requests.exceptions.ConnectionError("network down")
            return _raw_today_schema()

    monkeypatch.setitem(__import__("sys").modules, "akshare", FakeAk)
    result = provider.fetch_raw_sector_flow(attempts=2)
    assert calls["count"] == 2
    assert result.diagnostic["retry_count"] == 1
    assert result.raw_df is not None


def test_schema_drift_is_not_retried(monkeypatch):
    calls = {"count": 0}

    class FakeAk:
        __version__ = "test"

        @staticmethod
        def stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流"):
            calls["count"] += 1
            return pd.DataFrame({"未知": [1]})

    monkeypatch.setitem(__import__("sys").modules, "akshare", FakeAk)
    raw_result = provider.fetch_raw_sector_flow(attempts=3)
    with pytest.raises(provider.ProviderBoundaryError) as excinfo:
        provider.normalize_provider_dataframe(raw_result.raw_df, sector_type="行业资金流")
    assert excinfo.value.category == "schema_drift"
    assert calls["count"] == 1


def test_validate_provider_text_detects_forbidden_phrase():
    assert "未来会涨" in provider.validate_provider_text("未来会涨")
