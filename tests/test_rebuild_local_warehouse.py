from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.local_warehouse import connect_warehouse, query_warehouse_summary
from tools import rebuild_local_warehouse


def _write_snapshot(directory: Path, date: str = "2026-01-15") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"sector_flow_{date}.csv"
    pd.DataFrame(
        {
            "trade_date": [date, date],
            "captured_at": [f"{date} 10:00:00", f"{date} 10:00:00"],
            "captured_time": ["10:00:00", "10:00:00"],
            "sector_type": ["行业资金流", "行业资金流"],
            "sector_name": ["半导体", "银行"],
            "main_net_inflow_billion": [10.0, -3.0],
            "source": ["TEST", "TEST"],
        }
    ).to_csv(path, index=False)
    return path


def test_rebuild_local_warehouse_can_be_imported():
    assert hasattr(rebuild_local_warehouse, "build_parser")
    assert hasattr(rebuild_local_warehouse, "rebuild_local_warehouse")


def test_parser_accepts_expected_flags():
    parser = rebuild_local_warehouse.build_parser()
    args = parser.parse_args(
        [
            "--warehouse-path",
            "tmp.sqlite",
            "--include-local",
            "--include-sample",
            "--clear",
            "--dry-run",
            "--quiet",
        ]
    )
    assert args.warehouse_path == "tmp.sqlite"
    assert args.include_local is True
    assert args.include_sample is True
    assert args.clear is True
    assert args.dry_run is True
    assert args.quiet is True


def test_dry_run_does_not_create_sqlite_file(tmp_path):
    sample_dir = tmp_path / "sample"
    _write_snapshot(sample_dir)
    warehouse_path = tmp_path / "warehouse.sqlite"
    result = rebuild_local_warehouse.rebuild_local_warehouse(
        warehouse_path=str(warehouse_path),
        sample_dir=str(sample_dir),
        include_sample=True,
        dry_run=True,
        quiet=True,
    )
    assert result["dry_run"] is True
    assert result["summary_label"] == "dry-run 完成"
    assert not warehouse_path.exists()


def test_include_sample_rebuilds_temp_warehouse(tmp_path):
    sample_dir = tmp_path / "sample"
    _write_snapshot(sample_dir)
    warehouse_path = tmp_path / "warehouse.sqlite"
    result = rebuild_local_warehouse.rebuild_local_warehouse(
        warehouse_path=str(warehouse_path),
        sample_dir=str(sample_dir),
        include_sample=True,
        clear=True,
        quiet=True,
    )
    assert result["inserted_rows"] == 2
    assert warehouse_path.exists()
    conn = connect_warehouse(str(warehouse_path))
    try:
        summary = query_warehouse_summary(conn)
        assert summary["sample_row_count"] == 2
    finally:
        conn.close()


def test_default_does_not_import_local_dir_without_flag(tmp_path):
    local_dir = tmp_path / "local"
    sample_dir = tmp_path / "sample"
    _write_snapshot(local_dir, "2026-06-01")
    _write_snapshot(sample_dir, "2026-01-15")
    warehouse_path = tmp_path / "warehouse.sqlite"
    rebuild_local_warehouse.rebuild_local_warehouse(
        warehouse_path=str(warehouse_path),
        local_dir=str(local_dir),
        sample_dir=str(sample_dir),
        include_local=False,
        include_sample=True,
        quiet=True,
    )
    conn = connect_warehouse(str(warehouse_path))
    try:
        summary = query_warehouse_summary(conn)
        assert summary["local_row_count"] == 0
        assert summary["sample_row_count"] == 2
    finally:
        conn.close()


def test_script_does_not_write_csv_directories(tmp_path):
    local_dir = tmp_path / "local"
    sample_dir = tmp_path / "sample"
    local_csv = _write_snapshot(local_dir, "2026-06-01")
    sample_csv = _write_snapshot(sample_dir, "2026-01-15")
    before_local = local_csv.read_text(encoding="utf-8")
    before_sample = sample_csv.read_text(encoding="utf-8")
    rebuild_local_warehouse.rebuild_local_warehouse(
        warehouse_path=str(tmp_path / "warehouse.sqlite"),
        local_dir=str(local_dir),
        sample_dir=str(sample_dir),
        include_local=True,
        include_sample=True,
        quiet=True,
    )
    assert local_csv.read_text(encoding="utf-8") == before_local
    assert sample_csv.read_text(encoding="utf-8") == before_sample


def test_clear_rebuilds_source_without_accumulating_duplicates(tmp_path):
    sample_dir = tmp_path / "sample"
    _write_snapshot(sample_dir)
    warehouse_path = tmp_path / "warehouse.sqlite"
    rebuild_local_warehouse.rebuild_local_warehouse(
        warehouse_path=str(warehouse_path),
        sample_dir=str(sample_dir),
        include_sample=True,
        clear=True,
        quiet=True,
    )
    rebuild_local_warehouse.rebuild_local_warehouse(
        warehouse_path=str(warehouse_path),
        sample_dir=str(sample_dir),
        include_sample=True,
        clear=True,
        quiet=True,
    )
    conn = connect_warehouse(str(warehouse_path))
    try:
        summary = query_warehouse_summary(conn)
        assert summary["sample_row_count"] == 2
    finally:
        conn.close()


def test_missing_directory_returns_readable_warning(tmp_path):
    result = rebuild_local_warehouse.rebuild_local_warehouse(
        warehouse_path=str(tmp_path / "warehouse.sqlite"),
        sample_dir=str(tmp_path / "missing"),
        include_sample=True,
        quiet=True,
    )
    sample_result = result["sample_result"]
    assert sample_result["rebuild_label"] == "无可导入文件"
    assert sample_result["warnings"]


def test_script_source_does_not_import_akshare():
    source = Path(rebuild_local_warehouse.__file__).read_text(encoding="utf-8")
    assert "akshare" not in source.lower()
