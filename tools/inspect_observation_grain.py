from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.theme_dynamics import (  # noqa: E402
    CANONICAL_BUCKET_POLICY,
    CAPTURED_TIME_BUCKET_MINUTES,
    analyze_observation_bucket_collisions,
    build_bucket_collision_summary,
    build_theme_observation_events,
    get_bucketed_analytical_observation_grain,
    get_raw_event_observation_grain,
    materialize_canonical_observations,
)
from src.theme_taxonomy import get_theme_names, load_theme_taxonomy  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect read-only observation grain and bucket materialization evidence.")
    parser.add_argument("--source-mode", default="SAMPLE", choices=["SAMPLE", "REAL"])
    parser.add_argument("--data-dir", default=None, help="Optional CSV directory override.")
    parser.add_argument("--theme", default=None, help="Optional configured theme filter.")
    parser.add_argument("--date", default=None, help="Optional trade_date filter.")
    parser.add_argument("--mode", default=None, choices=["strict_representative", "representative", "breadth"], help="Optional calculation mode filter.")
    parser.add_argument("--bucket-minutes", type=int, default=CAPTURED_TIME_BUCKET_MINUTES)
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument("--events", action="store_true", help="Print compact raw event rows.")
    parser.add_argument("--collisions", action="store_true", help="Print collided bucket examples.")
    parser.add_argument("--canonical", action="store_true", help="Print compact canonical observation rows.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum example rows.")
    return parser


def _json_safe(value):
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _filter(df: pd.DataFrame, theme: str | None = None, date: str | None = None, mode: str | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    if theme and "theme_name" in work.columns:
        work = work[work["theme_name"].astype(str).eq(str(theme))]
    if date and "trade_date" in work.columns:
        work = work[work["trade_date"].astype(str).eq(str(date))]
    if mode and "calculation_mode" in work.columns:
        work = work[work["calculation_mode"].astype(str).eq(str(mode))]
    return work.reset_index(drop=True)


def _short_ids(values: object, limit: int = 4) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item)[:12] for item in values[:limit]]


def build_observation_grain_report(
    source_mode: str = "SAMPLE",
    data_dir: str | None = None,
    theme: str | None = None,
    date: str | None = None,
    mode: str | None = None,
    bucket_minutes: int = CAPTURED_TIME_BUCKET_MINUTES,
    limit: int = 10,
) -> dict:
    source_mode = str(source_mode or "SAMPLE").upper()
    taxonomy = load_theme_taxonomy()
    if theme and theme not in set(get_theme_names(taxonomy)):
        return {
            "source_mode": source_mode,
            "grain_available": False,
            "warnings": [f"未知主题：{theme}。"],
            "errors": [],
            "raw_event_grain": list(get_raw_event_observation_grain()),
            "bucketed_analytical_grain": list(get_bucketed_analytical_observation_grain()),
        }

    events = build_theme_observation_events(
        taxonomy=taxonomy,
        source_mode=source_mode,
        data_dir=data_dir,
        calculation_modes=[mode] if mode else None,
        bucket_minutes=bucket_minutes,
    )
    filtered_events = _filter(events, theme=theme, date=date, mode=mode)
    collisions = analyze_observation_bucket_collisions(filtered_events)
    canonical = materialize_canonical_observations(filtered_events, policy=CANONICAL_BUCKET_POLICY)
    summary = build_bucket_collision_summary(collisions)
    raw_grain = list(get_raw_event_observation_grain())
    bucket_grain = list(get_bucketed_analytical_observation_grain())
    true_duplicate_rows = int(filtered_events.duplicated(raw_grain, keep=False).sum()) if not filtered_events.empty else 0
    collided_examples = collisions[collisions.get("event_count", pd.Series(dtype=int)).fillna(0).astype(int).gt(1)].head(max(1, int(limit or 10)))
    canonical_examples = canonical.head(max(1, int(limit or 10))) if canonical is not None and not canonical.empty else pd.DataFrame()
    event_examples = filtered_events.head(max(1, int(limit or 10))) if not filtered_events.empty else pd.DataFrame()
    return {
        "source_mode": source_mode,
        "grain_available": bool(not filtered_events.empty),
        "raw_event_grain": raw_grain,
        "bucketed_analytical_grain": bucket_grain,
        "bucket_minutes": max(1, int(bucket_minutes or 1)),
        "materialization_policy": CANONICAL_BUCKET_POLICY,
        "raw_event_count": int(len(filtered_events)),
        "unique_raw_event_grain_count": int(filtered_events[raw_grain].drop_duplicates().shape[0]) if not filtered_events.empty else 0,
        "true_duplicate_event_row_count": true_duplicate_rows,
        "canonical_observation_count": int(len(canonical)),
        "non_selected_but_preserved_event_count": max(0, int(len(filtered_events)) - int(len(canonical))),
        "bucket_collision_summary": summary,
        "warnings": list(getattr(events, "attrs", {}).get("warnings", [])),
        "errors": [],
        "event_examples": event_examples[
            [column for column in ["theme_name", "trade_date", "captured_at", "captured_time", "captured_time_bucket", "calculation_mode", "event_observation_id", "snapshot_event_id"] if column in event_examples.columns]
        ].to_dict(orient="records")
        if not event_examples.empty
        else [],
        "collided_bucket_examples": [
            {
                "theme_name": row.get("theme_name"),
                "trade_date": row.get("trade_date"),
                "captured_time_bucket": row.get("captured_time_bucket"),
                "calculation_mode": row.get("calculation_mode"),
                "event_count": int(row.get("event_count", 0) or 0),
                "exact_captured_times": row.get("exact_captured_times") or [],
                "event_ids": _short_ids(row.get("event_observation_ids")),
                "snapshot_ids": _short_ids(row.get("snapshot_ids")),
                "state_codes": row.get("state_codes_represented") or [],
                "collision_type": row.get("collision_type"),
                "within_bucket_state_stable": bool(row.get("within_bucket_state_stable", True)),
            }
            for _, row in collided_examples.iterrows()
        ],
        "canonical_examples": canonical_examples[
            [
                column
                for column in [
                    "theme_name",
                    "trade_date",
                    "captured_time_bucket",
                    "calculation_mode",
                    "selected_captured_time",
                    "event_count",
                    "collision_type",
                    "bucket_stability_state",
                    "selected_event_observation_id",
                    "canonical_observation_id",
                ]
                if column in canonical_examples.columns
            ]
        ].to_dict(orient="records")
        if not canonical_examples.empty
        else [],
    }


def _print_report(report: dict, show_events: bool = False, show_collisions: bool = False, show_canonical: bool = False) -> None:
    print("Observation grain audit")
    print(f"  source_mode: {report.get('source_mode')}")
    print(f"  raw event grain: {' × '.join(report.get('raw_event_grain') or [])}")
    print(f"  bucketed analytical grain: {' × '.join(report.get('bucketed_analytical_grain') or [])}")
    print(f"  bucket width minutes: {report.get('bucket_minutes')}")
    print(f"  materialization policy: {report.get('materialization_policy')}")
    print(f"  raw events: {report.get('raw_event_count')}")
    print(f"  unique raw event grains: {report.get('unique_raw_event_grain_count')}")
    print(f"  true duplicate event rows: {report.get('true_duplicate_event_row_count')}")
    print(f"  canonical observations: {report.get('canonical_observation_count')}")
    print(f"  non-selected events preserved in lineage: {report.get('non_selected_but_preserved_event_count')}")
    summary = report.get("bucket_collision_summary") or {}
    print("Bucket collision summary")
    print(f"  buckets: {summary.get('bucket_count', 0)}")
    print(f"  collided buckets: {summary.get('collided_bucket_count', 0)}")
    print(f"  extra events inside collided buckets: {summary.get('extra_events_within_collided_buckets', 0)}")
    print(f"  max events per bucket: {summary.get('max_events_per_bucket', 0)}")
    print(f"  within-bucket state-change buckets: {summary.get('within_bucket_state_change_count', 0)}")
    print(f"  collision types: {summary.get('collision_type_counts', {})}")
    for warning in report.get("warnings") or []:
        print(f"  warning: {warning}")
    if show_events:
        print("Raw event examples")
        for row in report.get("event_examples") or []:
            print(f"  - {row}")
    if show_collisions:
        print("Collided bucket examples")
        for row in report.get("collided_bucket_examples") or []:
            print(f"  - {row}")
    if show_canonical:
        print("Canonical observation examples")
        for row in report.get("canonical_examples") or []:
            print(f"  - {row}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_observation_grain_report(
        source_mode=args.source_mode,
        data_dir=args.data_dir,
        theme=args.theme,
        date=args.date,
        mode=args.mode,
        bucket_minutes=args.bucket_minutes,
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(_json_safe(report), ensure_ascii=False, indent=2))
    else:
        _print_report(report, show_events=args.events, show_collisions=args.collisions, show_canonical=args.canonical)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
