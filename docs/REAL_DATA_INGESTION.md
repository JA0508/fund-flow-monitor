# Real Data Ingestion

This project is CSV-first. Real AKShare snapshots are collected locally, written to ignored CSV cache files, and then read by the Streamlit app for CACHE / HISTORY views.

SAMPLE data remains a public demo fallback. It is synthetic demo data and does not represent real market quotes.

## Data Source

The current real-data path uses:

```python
ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
```

The collector can also request other supported `sector_type` values, such as `概念资金流`, when AKShare supports them.

AKShare and Eastmoney are third-party/free data sources. Availability, column names, timing and network behavior may change. The app treats this path as a learning/prototype data source, not a production financial feed.

## Provider Boundary Diagnostics

v3.5 adds a lightweight AKShare provider adapter:

```text
AKShare provider call
-> provider response diagnostic
-> explicit schema mapping
-> controlled normalization
-> real snapshot contract
-> local CSV cache / audit log
```

The adapter currently uses:

```python
ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
```

It records safe schema metadata only:

- provider and API name
- response type
- row count
- returned column names
- normalized column names
- dtype summary
- schema fingerprint
- normalization status
- contract status when available
- concise failure category and message

It does not store the full raw market response in provider diagnostics.

Supported field mappings are explicit. Unknown columns are not guessed with fuzzy matching. If AKShare returns a schema that does not map to the required internal fields, the adapter reports `schema_drift` instead of silently choosing a column.

Provider-level failure categories include:

- `network_error`
- `timeout_error`
- `provider_error`
- `provider_parse_error`
- `empty_response`
- `schema_drift`
- `normalization_error`
- `contract_error`

Network and timeout errors may be retried with a small bounded retry count. Schema drift, normalization errors and contract errors are not retried because repeating the same call usually cannot fix a deterministic schema mismatch.

Run the probe without writing cache files:

```bash
.venv/bin/python tools/probe_akshare.py
.venv/bin/python tools/probe_akshare.py --json
.venv/bin/python tools/probe_akshare.py --raw-columns
```

The probe is diagnostic only. It does not write `data/ticks`, `sample_data`, SQLite or warehouse files.

## Collect One Real Snapshot

Dry run first:

```bash
.venv/bin/python tools/collect_real_snapshot.py --dry-run
```

`--dry-run` may still call AKShare, but it does not write `data/ticks`.

Write one real snapshot into the ignored local cache:

```bash
.venv/bin/python tools/collect_real_snapshot.py
```

The legacy command remains available and points to the same collection path:

```bash
.venv/bin/python tools/collect_market_snapshot.py
```

Output is written to:

```text
data/ticks/sector_flow_YYYY-MM-DD.csv
```

`data/ticks/*.csv` is ignored by Git and must not be committed.

## Inspect Real Cache Coverage

After collecting real snapshots locally, verify that the cache exists without committing it:

```bash
.venv/bin/python tools/verify_runtime.py
.venv/bin/python tools/smoke_check.py
git status --short
git check-ignore -v data/ticks/test.csv
git check-ignore -v data/logs/collector_runs.jsonl
```

The app also shows a compact evidence section in the `数据说明` tab:

- current view status: `LIVE`, `CACHE`, `HISTORY`, `SAMPLE`, `DEMO`, or `EMPTY`
- whether local real cache exists
- real snapshot file count and covered dates
- latest real cache date and captured time
- latest cache file modified time
- empty or malformed cache file counts
- cache staleness status: `fresh`, `stale`, `missing`, or `unknown`
- latest collector run status, if `data/logs/collector_runs.jsonl` exists

Freshness is a data-observability label only. It describes how recent the local CSV cache appears to be; it is not a trading signal and does not imply any future market direction.

## Collector Modes and Audit Log

The collector is a one-shot local command. It does not run inside Streamlit and it does not create a scheduler.

Common modes:

```bash
.venv/bin/python tools/collect_real_snapshot.py --no-network
.venv/bin/python tools/collect_real_snapshot.py --dry-run --no-log
.venv/bin/python tools/collect_real_snapshot.py --output-dir data/ticks
```

- `--no-network`: skips AKShare entirely, validates CLI/import behavior, and never writes `data/ticks`.
- `--dry-run`: fetches and validates when AKShare is available, but does not write `data/ticks`.
- `--no-log`: disables the collector audit log for the current run.
- `--output-dir`: changes the real CSV cache directory; the default remains `data/ticks`.

By default, each collector run writes one JSON object to:

```text
data/logs/collector_runs.jsonl
```

The audit log records:

- timestamp
- status
- row count
- written row count
- captured time
- trade date
- source / provider / API name
- output path
- contract and quality labels
- error category, when applicable
- short message

Possible collector statuses include:

- `success`
- `dry_run`
- `no_network`
- `fetch_error`
- `empty_fetch`
- `contract_error`
- `duplicate_skipped`
- `write_error`

Provider-level categories are preserved in `error_category` when available. For example, an upstream JSON parse failure inside AKShare is reported as `provider_parse_error`, while a returned DataFrame with unsupported columns is reported as `schema_drift`. A contract failure after successful normalization is reported separately as `contract_error`.

`data/logs/` and `logs/` are ignored by Git. Audit logs are local runtime artifacts and should not be committed.

If the audit log contains malformed lines, the reader reports warning counts and keeps any valid records. Public Streamlit Cloud and CI do not require this log to exist.

## Normalized Real Snapshot Schema

The normalized internal schema includes:

- `trade_date`
- `captured_at`
- `captured_time`
- `fetched_at`
- `sector_type`
- `rank_value`
- `sector_code`
- `sector_name`
- `change_pct`
- `main_net_inflow_yuan`
- `main_net_inflow_billion`
- `main_net_ratio`
- `super_large_net_inflow_yuan`
- `large_net_inflow_yuan`
- `medium_net_inflow_yuan`
- `small_net_inflow_yuan`
- `leading_stock`
- `source`
- `provider`
- `api_name`
- `data_mode`

For real AKShare snapshots:

- `source`: `AKShare / Eastmoney`
- `provider`: `AKShare / Eastmoney`
- `api_name`: `stock_sector_fund_flow_rank`
- `data_mode`: `REAL`

SAMPLE files use `data_mode=SAMPLE` and must stay under `sample_data/ticks`.

## Validation

Run real-data checks without writing:

```bash
.venv/bin/python tools/collect_real_snapshot.py --dry-run
```

Run the project quality gate:

```bash
.venv/bin/python tools/quality_gate.py
```

The collector validates normalized snapshots with:

- real snapshot data contracts
- snapshot quality checks
- duplicate detection before appending to CSV

Real data contracts are intentionally lightweight. They check required app columns and provenance markers, but they do not force SAMPLE markers on real/cache data.

## Collect Multiple Snapshots

The collector intentionally does not implement a long-running scheduler inside Streamlit. For repeated local collection during market hours, run the one-shot command manually or schedule it outside the app with tools such as cron, launchd, or another local scheduler.

Example manual sequence:

```bash
.venv/bin/python tools/collect_real_snapshot.py
.venv/bin/python tools/collect_real_snapshot.py
```

Duplicate `captured_time + sector_type + sector_name` rows are skipped by default.

## Troubleshooting

If AKShare fails:

- Confirm dependencies are installed with `.venv/bin/pip install -r requirements.txt`.
- Run `.venv/bin/python tools/probe_akshare.py` to inspect AKShare availability.
- Try again during market hours.
- Check whether upstream column names changed.
- Use SAMPLE mode for UI/demo work while real data is unavailable.

If the app shows `EMPTY` in real/cache mode:

- No readable real cache exists under `data/ticks`.
- Run `.venv/bin/python tools/collect_real_snapshot.py --dry-run`.
- If dry run passes, run `.venv/bin/python tools/collect_real_snapshot.py`.
- Switch to SAMPLE mode if you only need the public demo path.

## Streamlit Cloud Behavior

Streamlit Cloud public demo deployments usually do not include private real cache files. In that environment, the app should default to SAMPLE when real cache is unavailable.

This is expected:

- public demo: SAMPLE fallback
- local real usage: `data/ticks/*.csv` generated by AKShare collector
- local history replay: existing ignored CSV cache

## Future Path

SQLite warehouse remains a local rebuildable query index. Future versions may use the warehouse for richer historical queries, but CSV remains the source of truth for this MVP.

Do not commit real cache files, local SQLite files, credentials, or secrets.
