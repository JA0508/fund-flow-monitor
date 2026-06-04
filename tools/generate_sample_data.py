from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = PROJECT_ROOT / "sample_data/ticks"

SECTORS = [
    ("801080", "半导体", "示例芯片"),
    ("801081", "电子", "示例电子"),
    ("801770", "通信", "示例通信"),
    ("801771", "通信设备", "示例光模块"),
    ("801750", "计算机", "示例软件"),
    ("801760", "传媒", "示例传媒"),
    ("801751", "软件开发", "示例平台"),
    ("801730", "电池", "示例电池"),
    ("801731", "电力设备", "示例电气"),
    ("801732", "光伏设备", "示例光伏"),
    ("801780", "银行", "示例银行"),
    ("801950", "煤炭", "示例煤炭"),
    ("801160", "电力", "示例电力"),
    ("801161", "公用事业", "示例公用"),
    ("801120", "食品饮料", "示例消费"),
    ("801150", "医药生物", "示例医药"),
    ("801151", "医疗器械", "示例器械"),
    ("801740", "国防军工", "示例军工"),
    ("801193", "证券Ⅱ", "示例证券"),
    ("801194", "保险Ⅱ", "示例保险"),
]

TIME_POINTS = {
    "2026-01-15": ["09:35:00", "10:30:00", "11:20:00", "13:30:00", "14:50:00"],
    "2026-01-16": ["09:35:00", "10:30:00", "11:20:00", "13:30:00", "14:50:00"],
}

THEME_DRIFT = {
    "半导体": [18, 28, 38, 52, 68],
    "电子": [12, 18, 25, 36, 44],
    "通信": [8, 16, 24, 38, 50],
    "通信设备": [10, 22, 34, 48, 62],
    "计算机": [5, 12, 18, 25, 36],
    "传媒": [-3, 2, 8, 15, 20],
    "软件开发": [4, 9, 14, 20, 28],
    "电池": [-12, -20, -28, -36, -48],
    "电力设备": [-18, -28, -38, -52, -66],
    "光伏设备": [-10, -18, -24, -35, -42],
    "银行": [6, 8, 11, 14, 16],
    "煤炭": [3, 6, 10, 13, 15],
    "电力": [-2, 1, 3, 5, 8],
    "公用事业": [-1, 0, 2, 3, 6],
    "食品饮料": [-8, -11, -15, -19, -24],
    "医药生物": [-6, -10, -14, -20, -30],
    "医疗器械": [-3, -7, -10, -15, -22],
    "国防军工": [-5, -2, 4, 9, 14],
    "证券Ⅱ": [2, 8, 12, 18, 26],
    "保险Ⅱ": [-1, 3, 6, 8, 10],
}

DAY_OFFSET = {
    "2026-01-15": 0,
    "2026-01-16": -14,
}


def _build_rows_for_date(trade_date: str) -> list[dict]:
    rows = []
    for idx_time, captured_time in enumerate(TIME_POINTS[trade_date]):
        captured_at = f"{trade_date} {captured_time}"
        for idx_sector, (sector_code, sector_name, leading_stock) in enumerate(SECTORS):
            base = THEME_DRIFT[sector_name][idx_time] + DAY_OFFSET[trade_date]
            wave = ((idx_sector % 5) - 2) * 0.8
            value_billion = round(base + wave, 2)
            value_yuan = value_billion * 100_000_000
            change_pct = round(value_billion / 28 + (idx_sector % 3 - 1) * 0.25, 2)
            ratio = round(max(min(value_billion / 8, 12), -12), 2)
            rows.append(
                {
                    "trade_date": trade_date,
                    "captured_at": captured_at,
                    "captured_time": captured_time,
                    "sector_type": "行业资金流",
                    "sector_code": sector_code,
                    "sector_name": sector_name,
                    "change_pct": change_pct,
                    "main_net_inflow_yuan": value_yuan,
                    "main_net_inflow_billion": value_billion,
                    "main_net_ratio": ratio,
                    "super_large_net_inflow_yuan": value_yuan * 0.52,
                    "large_net_inflow_yuan": value_yuan * 0.28,
                    "medium_net_inflow_yuan": value_yuan * -0.13,
                    "small_net_inflow_yuan": value_yuan * -0.09,
                    "leading_stock": leading_stock,
                    "source": "SAMPLE",
                    "data_mode": "SAMPLE",
                }
            )
    return rows


def generate_sample_files(sample_dir: Path = SAMPLE_DIR) -> list[Path]:
    sample_dir.mkdir(parents=True, exist_ok=True)
    output_paths = []
    for trade_date in sorted(TIME_POINTS):
        df = pd.DataFrame(_build_rows_for_date(trade_date))
        path = sample_dir / f"sector_flow_{trade_date}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        output_paths.append(path)
    return output_paths


def main() -> int:
    paths = generate_sample_files()
    for path in paths:
        df = pd.read_csv(path)
        sector_counts = df["sector_type"].value_counts().to_dict() if "sector_type" in df.columns else {}
        print(
            f"{path.relative_to(PROJECT_ROOT)} | rows={len(df)} | "
            f"captured_time={df['captured_time'].nunique()} | sector_type={sector_counts}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
