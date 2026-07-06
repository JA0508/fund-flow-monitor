# Architecture

`fund-flow-monitor` is a Streamlit portfolio project for A-share sector and theme fund-flow observation. It is intentionally kept as a trustworthy Streamlit MVP: CSV is the source of truth, SAMPLE data is synthetic, SQLite is only a rebuildable local index, and the app does not provide trading actions or future market conclusions.

## System Overview

```text
AKShare / local CSV / SAMPLE CSV
        |
        v
data source + snapshot catalog
        |
        v
standard sector-flow DataFrame
        |
        +--> theme taxonomy + theme pool aggregation
        |         |
        |         v
        |   theme radar / intraday hotspots / multi-day trends
        |
        +--> optional local SQLite warehouse
                  |
                  v
            read-only explorer / theme history / demo brief summary
        |
        v
Streamlit UI + Markdown observation brief + release checks
```

The architecture favors explicit data-state labels over hidden automation. Public demo visitors should see SAMPLE data clearly marked as synthetic demonstration data; local users can still work with real CSV cache files if they collect them manually.

## Streamlit Entry Point

- `app.py` is the Streamlit entry point.
- The app remains a single Streamlit surface with tabs rather than a backend-plus-frontend system.
- Business logic is split into `src/` modules so theme aggregation, brief generation, warehouse querying, runtime profile detection, and release checks can be tested outside Streamlit.
- The UI reads existing files and in-memory DataFrames; it does not automatically rebuild SQLite or write real CSV cache files during public demo browsing.

## Data Source Layer

Key modules:

- `src/data_source.py`: live data fetch orchestration.
- `src/providers/akshare_sector_flow.py`: AKShare/Eastmoney provider adapter, schema fingerprinting, explicit column mapping and provider-boundary diagnostics.
- `src/concept_flow.py`: concept-flow helper logic.
- `src/transform.py`: raw AKShare/Eastmoney-style rows to the standard snapshot DataFrame.
- `src/data_contracts.py`: lightweight structural checks for snapshot and SAMPLE data.

The live path is optional but first-class for local real-data work. Current sector fund-flow collection uses AKShare's `stock_sector_fund_flow_rank` through a provider adapter, then normalizes rows with provenance fields such as provider, API name, fetched timestamp and `data_mode=REAL`. The adapter keeps the upstream boundary explicit: it records safe response metadata, builds a deterministic schema fingerprint, maps only known column variants and reports unsupported schemas as schema drift. If AKShare or a live fetch is unavailable, the app can still run with CACHE, HISTORY, SAMPLE, DEMO, or EMPTY states. The public Streamlit Cloud path should not depend on live fetch success.

## Runtime Profile Layer

Key module:

- `src/runtime_profile.py`

The runtime profile chooses safe initial defaults. In public demo mode or first-visit cloud scenarios without real local cache, it defaults to:

- `SAMPLE 演示样例数据`
- `作品集演示模式`
- no automatic writes to `data/ticks`
- no automatic writes to `data/warehouse`

This profile is a presentation and safety layer, not a new data source. User choices remain available in the sidebar.

## Storage And Cache Layer

Key modules:

- `src/storage.py`
- `src/snapshot_catalog.py`
- `src/snapshot_quality.py`
- `src/collection_policy.py`
- `src/ingestion_metrics.py`
- `tools/collect_market_snapshot.py`
- `tools/collect_real_snapshot.py`
- `tools/run_collection_session.py`

Real local cache lives under `data/ticks/*.csv` and is intentionally ignored by git. `tools/collect_real_snapshot.py` is the clearer manual local collection entry point and delegates to the existing one-shot collector. The Streamlit UI does not silently create real market CSV files for public visitors.

Collector run audit logs live under `data/logs/collector_runs.jsonl` by default. They record local run status and troubleshooting metadata for manual operations, and remain ignored runtime artifacts.

`src/snapshot_catalog.py` provides the read-only evidence layer for local real cache coverage. It summarizes available real cache dates, latest snapshot path/date/time, file modified time, empty or malformed cache files, cache staleness, and the latest collector audit-log status. This evidence layer only reads local CSV/log files; it does not fetch AKShare, write CSV, write logs, or create a database.

`tools/run_collection_session.py` is a bounded manual runner around the same one-shot collector. It uses `src/collection_policy.py` for local session/interval/attempt checks and `src/ingestion_metrics.py` for audit-log metrics. It is not a scheduler, daemon, backend service or Streamlit loop; it delegates actual provider fetch, validation and CSV writing to the existing collector path.

## Sample Data Layer

Key modules and files:

- `src/sample_data.py`
- `sample_data/ticks/*.csv`
- `sample_data/fund_profiles/sample_fund_profiles.csv`

SAMPLE data is tracked because it is synthetic and reproducible. It is used for GitHub and Streamlit Cloud demos, tests, screenshots, and static demo briefs. SAMPLE is never described as real market data.

## Theme Computation Layer

Key modules:

- `src/theme_taxonomy.py`
- `src/theme_pool.py`
- `src/theme_radar.py`
- `src/intraday_hotspots.py`
- `src/multi_day_trends.py`
- `src/theme_history.py`
- `src/theme_history_viz.py`

The theme layer maps sector-level rows into fund-oriented themes such as semiconductor, AI/TMT, new energy, medicine, consumption, dividend defense, defense industry, and securities/financial themes. The three observation modes are intentionally explicit:

- strict representative view
- representative view
- breadth observation

These modes describe historical or current sample states. They do not produce trading actions or future conclusions.

## Warehouse Layer

Key modules and tools:

- `src/local_warehouse.py`
- `src/warehouse_explorer.py`
- `tools/rebuild_local_warehouse.py`

SQLite is optional and local-only. It indexes existing CSV snapshots so the app can query source types, dates, captured times, and theme history. It is not a mandatory production database, not a cloud database, and not the source of truth.

The public demo works without `data/warehouse/fund_flow.sqlite`. If users want warehouse-powered panels locally, they can rebuild the index from tracked SAMPLE data:

```bash
python tools/rebuild_local_warehouse.py --include-sample --clear
```

## UI And Component Layer

Key modules:

- `app.py`
- `src/ui_components.py`
- `src/chart.py`
- `src/presentation.py`

The UI uses Streamlit and Plotly for dark-mode financial dashboard views. Reusable rendering helpers keep status cards, tables, brief previews, warehouse panels, and theme history visuals consistent. UI panels should disclose data status first, then show charts and tables.

## Observation Brief Layer

Key modules:

- `src/insight_brief.py`
- `src/brief_templates.py`
- `src/theme_history_brief.py`
- `tools/export_sample_brief.py`

Observation briefs are Markdown outputs. The SAMPLE demo brief is generated from tracked SAMPLE CSV through a temporary warehouse path and does not read `data/ticks` or default `data/warehouse`.

## Validation And Release-Check Layer

Key modules and tools:

- `src/release_readiness.py`
- `tools/release_check.py`
- `tools/cloud_preflight.py`
- `tools/smoke_check.py`
- `tools/verify_runtime.py`
- `tests/`

These checks focus on public portfolio safety:

- required public assets exist
- SAMPLE notices are present
- README and docs links are valid
- forbidden local data and database files are not tracked
- SAMPLE snapshot CSVs satisfy a lightweight data contract
- public demo defaults are consistent

## Public Demo Data Flow

```text
sample_data/ticks/*.csv
        |
        v
sample catalog + data contract check
        |
        v
theme pool / radar / hotspots / multi-day panels
        |
        v
Streamlit portfolio mode + demo brief
```

Public demo mode does not trigger AKShare, does not write `data/ticks`, and does not create the default SQLite warehouse.

## Local Real / Cache Data Flow

```text
manual collect tool or existing local CSV
        |
        v
data/ticks/sector_flow_YYYY-MM-DD.csv
        |
        v
snapshot catalog + quality report
        |
        v
theme radar / historical replay / optional warehouse index
```

Local real cache remains private and ignored by git. Users can rebuild SQLite locally from these CSVs when they explicitly request it.

## Why There Is No Mandatory Production Database

This project is a portfolio-grade Streamlit MVP, not a production financial data platform. A mandatory production database would add operational complexity without improving the public demo's core message. CSV-first storage keeps the project auditable, portable, and easy to inspect.

SQLite is included only as a rebuildable local query index for historical exploration. The app can run without it.

## Historical Evidence Layer

v3.7 adds a read-only historical evidence layer on top of persisted CSV snapshots:

- `src/history_evidence.py` scans `sector_flow_YYYY-MM-DD.csv` files and reconstructs snapshot evidence records.
- Evidence records include relative file path, deterministic snapshot ID, file hash, schema fingerprint, provider/API metadata when present, data contract status, captured_time coverage and source mode.
- `tools/inspect_history_evidence.py` provides a local CLI for coverage and replay provenance checks.
- The Streamlit multi-day tab and data explanation tab show evidence summaries and captured_time coverage matrices.

This layer does not change theme calculations, does not read from AKShare, does not write CSV or SQLite, and does not perform performance analysis or prediction. It exists to make historical replay provenance explicit.

## If This Became Production-Grade

A production-grade version would need additional systems that are intentionally out of scope here:

- scheduled ingestion with retry and monitoring
- data lineage and freshness SLAs
- a durable warehouse with migration management
- API service boundaries
- access control if user-specific data exists
- secrets management and observability
- stronger data quality rules and alerting
- legal/compliance review for any financial product language

Those additions should be justified by a real product requirement. They are not needed for the current public portfolio demo.
