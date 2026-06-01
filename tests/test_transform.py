from datetime import datetime

import math
import pandas as pd
import pytz

from src.transform import normalize_sector_flow
from src.utils import safe_to_float


def test_safe_to_float_plain_and_units():
    assert safe_to_float("1,234.5") == 1234.5
    assert safe_to_float("1.2亿") == 120000000
    assert safe_to_float("-3.5万") == -35000
    assert safe_to_float("12.3%") == 12.3
    assert math.isnan(safe_to_float("--"))


def test_normalize_chinese_fields_and_billion_conversion():
    raw = pd.DataFrame(
        [
            {
                "板块代码": "BK001",
                "板块名称": "半导体",
                "涨跌幅": "1.25%",
                "主力净流入-净额": "2.5亿",
                "主力净流入-净占比": "3.2%",
                "超大单净流入-净额": "1亿",
                "大单净流入-净额": "5000万",
                "中单净流入-净额": "-2000万",
                "小单净流入-净额": "-1000万",
                "主力净流入最大股": "中芯国际",
            }
        ]
    )
    captured_at = pytz.timezone("Asia/Shanghai").localize(datetime(2026, 5, 29, 10, 47))
    df = normalize_sector_flow(raw, "行业资金流", captured_at)
    assert df.loc[0, "sector_code"] == "BK001"
    assert df.loc[0, "sector_name"] == "半导体"
    assert df.loc[0, "main_net_inflow_yuan"] == 250000000
    assert df.loc[0, "main_net_inflow_billion"] == 2.5
    assert df.loc[0, "captured_time"] == "10:47:00"
    assert df.loc[0, "trade_date"] == "2026-05-29"


def test_missing_fields_do_not_crash():
    raw = pd.DataFrame([{"板块名称": "电力", "主力净流入-净额": 100000000}])
    df = normalize_sector_flow(raw, "行业资金流", datetime(2026, 5, 29, 10, 0))
    assert len(df) == 1
    assert df.loc[0, "sector_code"] == ""
    assert pd.isna(df.loc[0, "change_pct"])


def test_missing_name_or_amount_is_dropped():
    raw = pd.DataFrame(
        [
            {"板块名称": None, "主力净流入-净额": 100000000},
            {"板块名称": "有效", "主力净流入-净额": "--"},
            {"板块名称": "保留", "主力净流入-净额": 100000000},
        ]
    )
    df = normalize_sector_flow(raw, "行业资金流", datetime(2026, 5, 29, 10, 0))
    assert df["sector_name"].tolist() == ["保留"]

