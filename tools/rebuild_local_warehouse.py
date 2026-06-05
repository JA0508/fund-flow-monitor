from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.local_warehouse import (  # noqa: E402
    audit_warehouse,
    connect_warehouse,
    get_default_warehouse_path,
    initialize_warehouse,
    query_warehouse_summary,
    rebuild_warehouse_from_csv_directory,
)
from src.snapshot_quality import build_snapshot_file_catalog  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从本地 CSV 重建 SQLite warehouse 查询索引。")
    parser.add_argument("--warehouse-path", default=get_default_warehouse_path(), help="SQLite warehouse 输出路径。")
    parser.add_argument("--local-dir", default="data/ticks", help="本地真实 CSV 缓存目录。")
    parser.add_argument("--sample-dir", default="sample_data/ticks", help="SAMPLE 合成演示 CSV 目录。")
    parser.add_argument("--include-local", action="store_true", help="导入 data/ticks 本地真实缓存。默认不导入。")
    parser.add_argument("--include-sample", action="store_true", default=True, help="导入 sample_data/ticks 合成演示数据。")
    parser.add_argument("--no-sample", action="store_false", dest="include_sample", help="不导入 SAMPLE 数据。")
    parser.add_argument("--clear", action="store_true", help="导入前清理对应 source_type 的旧记录。")
    parser.add_argument("--dry-run", action="store_true", help="只扫描并输出计划，不创建或写入 SQLite。")
    parser.add_argument("--quiet", action="store_true", help="减少命令行输出。")
    return parser


def _scan_directory(directory: str, source_type: str) -> dict:
    catalog = build_snapshot_file_catalog(directory, pattern="sector_flow_*.csv")
    return {
        "source_type": source_type,
        "directory": directory,
        "file_count": int(len(catalog)),
        "imported_file_count": 0,
        "skipped_file_count": 0,
        "inserted_rows": 0,
        "skipped_duplicate_rows": 0,
        "warning_count": 0 if not catalog.empty else 1,
        "error_count": 0,
        "imported_files": [],
        "errors": [],
        "warnings": [] if not catalog.empty else [f"目录无可导入 CSV：{directory}"],
        "rebuild_label": "dry-run 扫描完成" if not catalog.empty else "无可导入文件",
        "rebuild_reason": "dry-run 只扫描 CSV 文件，不创建 SQLite，不写入数据。",
    }


def rebuild_local_warehouse(
    warehouse_path: str = get_default_warehouse_path(),
    local_dir: str = "data/ticks",
    sample_dir: str = "sample_data/ticks",
    include_local: bool = False,
    include_sample: bool = True,
    clear: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
) -> dict:
    results = {
        "warehouse_path": warehouse_path,
        "include_local": include_local,
        "include_sample": include_sample,
        "dry_run": dry_run,
        "local_result": None,
        "sample_result": None,
        "inserted_rows": 0,
        "warning_count": 0,
        "error_count": 0,
        "summary_label": "未执行",
    }
    if dry_run:
        if include_local:
            results["local_result"] = _scan_directory(local_dir, "LOCAL")
        if include_sample:
            results["sample_result"] = _scan_directory(sample_dir, "SAMPLE")
        for item in (results.get("local_result"), results.get("sample_result")):
            if item:
                results["warning_count"] += int(item.get("warning_count", 0) or 0)
                results["error_count"] += int(item.get("error_count", 0) or 0)
        results["summary_label"] = "dry-run 完成"
        if not quiet:
            _print_result(results)
        return results

    conn = connect_warehouse(warehouse_path)
    try:
        initialize_warehouse(conn)
        if include_local:
            results["local_result"] = rebuild_warehouse_from_csv_directory(conn, local_dir, "LOCAL", clear_source=clear)
        if include_sample:
            results["sample_result"] = rebuild_warehouse_from_csv_directory(conn, sample_dir, "SAMPLE", clear_source=clear)
        for item in (results.get("local_result"), results.get("sample_result")):
            if item:
                results["inserted_rows"] += int(item.get("inserted_rows", 0) or 0)
                results["warning_count"] += int(item.get("warning_count", 0) or 0)
                results["error_count"] += int(item.get("error_count", 0) or 0)
        summary = query_warehouse_summary(conn)
        audit = audit_warehouse(conn)
        results["summary_label"] = summary.get("warehouse_label")
        results["warehouse_summary"] = summary
        results["warehouse_audit"] = audit
    finally:
        conn.close()
    if not quiet:
        _print_result(results)
    return results


def _print_source_result(name: str, result: dict | None) -> None:
    if not result:
        print(f"{name}: 未启用")
        return
    print(f"{name}: {result.get('rebuild_label')}")
    print(f"  directory: {result.get('directory')}")
    print(f"  files: {result.get('imported_file_count')}/{result.get('file_count')}")
    print(f"  inserted_rows: {result.get('inserted_rows')}")
    print(f"  skipped_duplicate_rows: {result.get('skipped_duplicate_rows')}")
    print(f"  warnings/errors: {result.get('warning_count')} / {result.get('error_count')}")


def _print_result(result: dict) -> None:
    print("SQLite warehouse rebuild")
    print(f"  warehouse_path: {result.get('warehouse_path')}")
    print(f"  include_local: {result.get('include_local')}")
    print(f"  include_sample: {result.get('include_sample')}")
    print(f"  dry_run: {result.get('dry_run')}")
    _print_source_result("LOCAL", result.get("local_result"))
    _print_source_result("SAMPLE", result.get("sample_result"))
    print(f"  inserted_rows: {result.get('inserted_rows')}")
    print(f"  warning_count: {result.get('warning_count')}")
    print(f"  error_count: {result.get('error_count')}")
    print(f"  summary_label: {result.get('summary_label')}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = rebuild_local_warehouse(
        warehouse_path=args.warehouse_path,
        local_dir=args.local_dir,
        sample_dir=args.sample_dir,
        include_local=args.include_local,
        include_sample=args.include_sample,
        clear=args.clear,
        dry_run=args.dry_run,
        quiet=args.quiet,
    )
    return 1 if int(result.get("error_count", 0) or 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
