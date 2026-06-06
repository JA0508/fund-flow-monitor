from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.brief_templates import validate_brief_template_text
from tools import export_sample_brief


def _write_sample_csvs(sample_dir: Path) -> None:
    sample_dir.mkdir(parents=True, exist_ok=True)
    sectors = [
        ("半导体", 42.0),
        ("计算机", 18.0),
        ("通信", 12.0),
        ("电池", -8.0),
        ("银行", 25.0),
        ("医药生物", -12.0),
        ("国防军工", 6.0),
        ("证券Ⅱ", 9.0),
    ]
    for date, multiplier in (("2026-01-15", 0.7), ("2026-01-16", 1.0)):
        rows = []
        for time_index, captured_time in enumerate(("09:30:00", "10:30:00", "14:30:00"), start=1):
            for idx, (sector_name, base_value) in enumerate(sectors, start=1):
                value = base_value * multiplier + (time_index - 2) * 2
                rows.append(
                    {
                        "trade_date": date,
                        "captured_at": f"{date} {captured_time}",
                        "captured_time": captured_time,
                        "sector_type": "行业资金流",
                        "sector_code": f"S{idx:03d}",
                        "sector_name": sector_name,
                        "change_pct": round(value / 100, 2),
                        "main_net_inflow_yuan": value * 100_000_000,
                        "main_net_inflow_billion": value,
                        "main_net_ratio": round(value / 10, 2),
                        "super_large_net_inflow_yuan": value * 50_000_000,
                        "large_net_inflow_yuan": value * 30_000_000,
                        "medium_net_inflow_yuan": value * 10_000_000,
                        "small_net_inflow_yuan": value * 10_000_000,
                        "leading_stock": f"样例股{idx}",
                        "source": "SAMPLE",
                        "data_mode": "SAMPLE",
                    }
                )
        pd.DataFrame(rows).to_csv(sample_dir / f"sector_flow_{date}.csv", index=False)


def test_export_sample_brief_importable():
    assert hasattr(export_sample_brief, "export_sample_brief")
    assert hasattr(export_sample_brief, "build_parser")


def test_export_sample_brief_parser():
    parser = export_sample_brief.build_parser()
    args = parser.parse_args(
        [
            "--output",
            "x.md",
            "--template",
            "portfolio",
            "--sample-dir",
            "sample_data/ticks",
            "--theme-mode",
            "代表口径",
            "--quiet",
        ]
    )
    assert args.output == "x.md"
    assert args.template == "portfolio"
    assert args.sample_dir == "sample_data/ticks"
    assert args.include_theme_history is True
    assert args.theme_mode == "代表口径"
    assert args.quiet is True


def test_export_sample_brief_writes_tmp_output_without_data_ticks(tmp_path):
    sample_dir = tmp_path / "sample_data" / "ticks"
    _write_sample_csvs(sample_dir)
    output = tmp_path / "briefs" / "sample_observation_brief.md"
    default_warehouse = Path("data/warehouse/fund_flow.sqlite")
    before_exists = default_warehouse.exists()
    before_mtime = default_warehouse.stat().st_mtime if before_exists else None
    result = export_sample_brief.export_sample_brief(
        output=output,
        template="portfolio",
        sample_dir=sample_dir,
        quiet=True,
    )
    assert result["ok"] is True
    assert output.exists()
    assert not (tmp_path / "data" / "ticks").exists()
    text = output.read_text(encoding="utf-8")
    assert "SAMPLE" in text
    assert "合成演示数据" in text
    assert "不构成投资建议" in text
    assert "不预测未来走势" in text
    assert "主题历史观察摘要" in text
    assert "/Users/" not in text
    assert "Desktop/vibe coding" not in text
    assert validate_brief_template_text(text) == []
    assert not (tmp_path / "data" / "warehouse").exists()
    if before_exists:
        assert default_warehouse.exists()
        assert default_warehouse.stat().st_mtime == before_mtime
    else:
        assert not default_warehouse.exists()


def test_export_sample_brief_can_disable_theme_history(tmp_path):
    sample_dir = tmp_path / "sample_data" / "ticks"
    _write_sample_csvs(sample_dir)
    output = tmp_path / "briefs" / "sample_observation_brief.md"
    result = export_sample_brief.export_sample_brief(
        output=output,
        template="portfolio",
        sample_dir=sample_dir,
        include_theme_history=False,
        quiet=True,
    )
    assert result["ok"] is True
    text = output.read_text(encoding="utf-8")
    assert "主题历史观察摘要" not in text
    assert "SAMPLE" in text


def test_export_sample_brief_missing_sample_dir_returns_cli_error(tmp_path):
    output = tmp_path / "missing.md"
    code = export_sample_brief.main(
        [
            "--output",
            str(output),
            "--sample-dir",
            str(tmp_path / "missing_sample"),
            "--quiet",
        ]
    )
    assert code == 1
    assert not output.exists()
    assert not (tmp_path / "data" / "ticks").exists()
