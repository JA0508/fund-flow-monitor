from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    try:
        import akshare as ak
    except ImportError as exc:
        print(f"AKShare import failed: {exc}")
        return 1

    print(f"akshare version: {getattr(ak, '__version__', 'unknown')}")
    has_api = hasattr(ak, "stock_sector_fund_flow_rank")
    print(f"has stock_sector_fund_flow_rank: {has_api}")
    if not has_api:
        return 1

    for sector_type in ("行业资金流", "概念资金流"):
        print(f"\n=== {sector_type} 今日 前 5 行 ===")
        try:
            df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type=sector_type)
            print(df.head(5).to_string(index=False))
            print(f"columns: {list(df.columns)}")
        except Exception as exc:
            print(f"fetch failed for {sector_type}: {exc}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

