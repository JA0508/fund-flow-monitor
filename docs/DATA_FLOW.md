# Data Flow

This document explains how `fund-flow-monitor` moves from raw sector fund-flow snapshots to fund-oriented theme observations. It also records the trust boundary between real local cache, synthetic SAMPLE data, optional DEMO data, and optional SQLite warehouse indexes.

## Data Modes

The app uses explicit data-state labels so visitors can see what they are looking at.

| Mode | Meaning | Public Demo Role |
| --- | --- | --- |
| `LIVE` | A current live fetch succeeded during the session. | Optional, not required for public demo. |
| `CACHE` | The latest local real CSV cache is used. | Local-only, ignored by git. |
| `HISTORY` | A selected local CSV date is replayed. | Local-only unless using SAMPLE history. |
| `SAMPLE` | Tracked synthetic CSV under `sample_data/ticks`. | Default public demo path. |
| `DEMO` | In-memory UI demonstration data. | Useful fallback, not real data. |
| `EMPTY` | No usable data for the selected path. | Should be readable, not a crash. |

SAMPLE and DEMO must always be described as non-real-market data.

## Standard Snapshot Shape

The main sector-flow DataFrame is expected to include:

- `trade_date`
- `captured_at`
- `captured_time`
- `sector_type`
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

`src/data_contracts.py` checks the minimum practical contract without making the app overly brittle. The required columns for theme computation are:

- `captured_time`
- `sector_type`
- `sector_name`
- `main_net_inflow_billion`

SAMPLE files additionally require `source=SAMPLE` and `data_mode=SAMPLE`.

## Raw Data To Theme Observation

```text
raw sector / concept rows
        |
        v
normalized snapshot DataFrame
        |
        v
latest sector frame or historical frame
        |
        v
theme taxonomy mapping
        |
        v
theme pool aggregation
        |
        v
theme radar / hotspots / trends / brief
```

The theme taxonomy is configured in `config/theme_taxonomy.json`. It maps raw industry and concept names into fund-facing themes. The theme layer keeps multiple observation modes so the user can distinguish core representative sectors from broader related-sector observation.

## Tracked Data Files

The following files are intentionally tracked:

- `sample_data/ticks/*.csv`
- `sample_data/fund_profiles/sample_fund_profiles.csv`
- `config/theme_taxonomy.json`
- `config/fund_profiles.json`
- `config/watchlist.json`
- `docs/demo_briefs/sample_observation_brief.md`

These files make the public demo reproducible.

## Ignored Data Files

The following files are intentionally ignored:

- `data/ticks/*.csv`
- `data/warehouse/`
- `*.sqlite`
- `*.sqlite3`
- `*.db`
- `.env`
- `.venv/`
- `.streamlit/secrets.toml`

Real local CSV cache and local SQLite indexes should not enter git history.

## Real Local Cache

Real cache files are local CSV snapshots created or supplied by the user. They live under `data/ticks`. The app may read them for CACHE or HISTORY views, but they remain private and ignored.

When real cache exists, local users can inspect:

- latest intraday curve
- theme radar
- historical replay
- multi-day trends
- optional local SQLite warehouse index

The project does not read brokerage accounts or personal holdings.

## SAMPLE Data

SAMPLE data is synthetic. It is designed to make GitHub and Streamlit Cloud review possible without real cache, secrets, or network access. SAMPLE is used by:

- public demo runtime defaults
- screenshots
- demo brief export
- tests
- cloud preflight checks

SAMPLE is suitable for demonstrating data flow and UI behavior, but it does not represent real market quotes.

## SQLite Warehouse

SQLite is a rebuildable local query index. It is created only by explicit local commands such as:

```bash
python tools/rebuild_local_warehouse.py --include-sample --clear
```

The app should not require SQLite to start. Public demo mode should remain friendly when `data/warehouse/fund_flow.sqlite` is absent.

## Streamlit Cloud Behavior

On Streamlit Cloud, the expected first-visit path is:

1. no real local `data/ticks/*.csv`
2. tracked SAMPLE CSV available
3. runtime profile defaults to SAMPLE and portfolio presentation mode
4. UI clearly labels SAMPLE as synthetic demonstration data
5. warehouse panels show read-only unavailable states unless a local index exists

The app must not create fake real cache files to avoid EMPTY. If SAMPLE is missing, the correct behavior is a readable warning, not fabricated data.

## Data Freshness Limits

CSV snapshots are point-in-time files. CACHE and HISTORY only describe the files available locally. SAMPLE describes a synthetic scenario. The project does not make future conclusions from these states.

Freshness and trust should be interpreted from the visible data mode:

- `LIVE`: session-level freshness depends on upstream fetch success.
- `CACHE`: freshness depends on the local CSV timestamp/date.
- `HISTORY`: explicitly selected historical file.
- `SAMPLE`: synthetic demo only.
- `DEMO`: in-memory UI demonstration only.

## Practical Reasoning Guide

Use SAMPLE when reviewing the project as a public portfolio artifact. Use CACHE/HISTORY when running locally with private real CSV snapshots. Rebuild SQLite only when historical query panels are useful. Treat CSV as the source of truth in this MVP.
