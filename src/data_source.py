from __future__ import annotations

import pandas as pd


def fetch_sector_flow(sector_type: str, indicator: str = "今日") -> pd.DataFrame:
    """Fetch raw Eastmoney sector fund-flow ranking data through AKShare."""
    try:
        import akshare as ak
    except ImportError as exc:
        raise RuntimeError("AKShare 未安装，请先运行 pip install -r requirements.txt") from exc

    try:
        if not hasattr(ak, "stock_sector_fund_flow_rank"):
            raise AttributeError("当前 AKShare 版本缺少 stock_sector_fund_flow_rank 接口")
        data = ak.stock_sector_fund_flow_rank(indicator=indicator, sector_type=sector_type)
    except Exception as exc:
        raise RuntimeError(
            f"AKShare 获取 {sector_type} {indicator} 数据失败：{exc}"
        ) from exc

    if not isinstance(data, pd.DataFrame):
        raise RuntimeError("AKShare 返回结果不是 DataFrame，请检查接口版本")
    if data.empty:
        raise RuntimeError(f"AKShare 返回空数据：{sector_type} {indicator}")
    return data

