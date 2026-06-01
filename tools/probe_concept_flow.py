from __future__ import annotations


def main() -> int:
    try:
        import akshare as ak
    except ImportError:
        print("AKShare 未安装，请先运行 pip install -r requirements.txt")
        return 1

    print(f"akshare version: {getattr(ak, '__version__', 'unknown')}")
    has_api = hasattr(ak, "stock_sector_fund_flow_rank")
    print(f"has stock_sector_fund_flow_rank: {has_api}")
    if not has_api:
        return 1

    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="概念资金流")
    except Exception as exc:
        print(f"概念资金流接口请求失败: {exc}")
        return 1

    print("概念资金流 今日 前 5 行:")
    if df is None or df.empty:
        print("<empty>")
        return 1
    print(df.head(5).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
