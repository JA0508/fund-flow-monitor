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
- `provider`
- `api_name`
- `data_mode`
- `fetched_at`
- `rank_value`

`src/data_contracts.py` checks the minimum practical contract without making the app overly brittle. The required columns for theme computation are:

- `captured_time`
- `sector_type`
- `sector_name`
- `main_net_inflow_billion`

SAMPLE files additionally require `source=SAMPLE` and `data_mode=SAMPLE`.

Real AKShare snapshots use the same core shape but are validated by a separate real snapshot contract. Real rows should not contain SAMPLE or DEMO markers. Recommended provenance fields such as `provider`, `api_name`, `data_mode=REAL` and `fetched_at` improve cache observability, but the contract remains lightweight so future AKShare column drift does not break the app unnecessarily.

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

The primary local collector entry point is:

```bash
python tools/collect_real_snapshot.py
```

It calls the same underlying collector as `tools/collect_market_snapshot.py`: fetch AKShare sector fund-flow data, diagnose the provider response, normalize Chinese columns into the internal schema, validate the real snapshot contract, and append safely to `data/ticks/sector_flow_YYYY-MM-DD.csv`. `--dry-run` validates and summarizes without writing.

The live provider boundary is:

```text
ak.stock_sector_fund_flow_rank(...)
-> response type / columns / dtype / schema fingerprint
-> explicit AKShare column mapping
-> normalized internal snapshot
-> real data contract
```

Provider failures and data contract failures are separate. Network, timeout or upstream parse failures happen before a project-owned DataFrame exists. `schema_drift` means AKShare returned a DataFrame but its columns did not match any controlled mapping. `contract_error` means normalization succeeded but the internal snapshot failed project contract checks.

Collector runs are classified with explicit statuses such as `success`, `dry_run`, `no_network`, `fetch_error`, `empty_fetch`, `contract_error`, `duplicate_skipped` and `write_error`. Provider-level error categories include `network_error`, `timeout_error`, `provider_parse_error`, `empty_response`, `schema_drift`, `normalization_error` and `contract_error`. By default, the command appends a local JSONL audit entry to `data/logs/collector_runs.jsonl`; these logs are ignored and are not part of the public dataset.

`tools/run_collection_session.py` can run the one-shot collector a finite number of times for local manual collection. It does not add a new data source and does not create a background scheduler. It reads `src/collection_policy.py` for local eligibility decisions and emits a session summary with status counts, failure categories and created snapshot paths. Actual CSV writes still go through `tools/collect_market_snapshot.py` and `src/storage.py`.

The read-only cache evidence path uses `src/snapshot_catalog.py` to answer:

- whether real local cache exists
- how many snapshot CSV files and dates are available
- which cache date/time is latest
- whether any cache files are empty or malformed
- whether the latest cache appears fresh, stale, missing, or unknown
- what the latest collector run status was, if a local audit log exists

`src/ingestion_metrics.py` adds read-only ingestion run metrics on top of the audit log. Its success-rate denominator is write-intent runs: `dry_run` and `no_network` are excluded because they are validation modes, not real cache write attempts.

This is data provenance and runtime observability, not a market signal. Missing real cache on Streamlit Cloud is expected because real `data/ticks` and `data/logs` are private local runtime artifacts.

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

## Historical Coverage and Replay Provenance

v3.7 adds a historical evidence pass that reads existing CSV snapshots and reports:

- how many snapshot files are readable, empty or malformed
- which trade dates and captured_time buckets are covered
- provider/API/source/data_mode metadata if the CSV includes it
- schema fingerprint counts recovered from CSV columns
- data contract pass/fail counts
- replay evidence for a selected trade date

The coverage matrix uses `trade_date` as rows and minute-level `captured_time` buckets as columns by default. Values are snapshot counts, not market scores. This matrix is for lineage and replay coverage only; it is not a signal or model.

## Theme Observation Evidence

v3.8 connects the historical evidence layer to theme calculation lineage:

```text
CSV snapshot rows
-> theme_taxonomy.json definition fingerprint
-> canonical theme_pool matching
-> selected calculation mode inputs
-> aggregate value
-> threshold mapping
-> displayed theme state
-> compact evidence trace
```

The evidence trace is generated from the same calculation helpers as the displayed theme result. It records which configured members matched, which rows were included by the selected mode, which rows were excluded, the aggregate input values and the threshold table used for the displayed state.

For historical support, evidence keeps separate:

- cross-date history span
- intraday captured_time depth
- coverage consistency across dates

REAL and SAMPLE evidence are not silently combined. SAMPLE evidence remains synthetic demonstration evidence and must be read with that label visible.

## Theme Taxonomy Calibration Audit

v3.9 adds a read-only audit path for theme taxonomy calibration:

```text
config/theme_taxonomy.json
-> normalized theme member definitions
-> deterministic alias / canonical-name resolution
-> overlap audit + source-universe coverage audit
-> Data Explanation panel / audit_theme_taxonomy.py
```

The audit keeps `primary_sectors` and `related_sectors` compatible, but represents them internally as member definitions with role, strict-representative flag, mapping source, mapping method and rationale. It reports reused canonical members, ambiguous source rows, overlap pairs and per-theme calibration summaries.

Coverage is calculated against the selected source universe:

- SAMPLE coverage uses `sample_data/ticks` and remains synthetic demo evidence.
- REAL coverage uses local `data/ticks` if available and remains local cache evidence.
- SAMPLE and REAL coverage are not combined.
- The coverage denominator is the number of unique normalized source names visible in the selected latest snapshot set.

This audit does not modify the taxonomy, does not infer fuzzy matches, does not create formal industry labels and does not interpret coverage as market quality.

## Theme Dynamics Cube

v3.10 adds a theme-level dynamics pass. v3.11 makes the observation grain explicit and inserts a canonical materialization step:

```text
CSV snapshot rows
-> physical snapshot events
-> raw theme observation events
-> bucket collision analysis
-> canonical bucket observations
-> state transition trace / cross-date evolution / scope divergence / member structural divergence
-> Multi-Day evidence panel / inspect_theme_dynamics.py / brief section
```

Raw event grain is `snapshot_event_id × theme × calculation_mode × source_mode × theme_definition_fingerprint`. Bucketed analytical grain is `theme × trade_date × captured_time_bucket × calculation_mode × source_mode × taxonomy_fingerprint × theme_definition_fingerprint`.

The cube keeps SAMPLE and REAL source modes separate and includes taxonomy and theme-definition fingerprints in the observation grain. This prevents rows from different mapping versions or data sources from being interpreted as one continuous series.

The materialization policy is `latest_valid_snapshot_in_bucket`. It is deterministic, records selected event IDs, preserves non-selected contributing event IDs and does not average or sum cumulative "今日" snapshots. Multiple captured events inside one minute bucket are reported as bucket collisions; true raw event duplicates are counted separately.

The cross-date view uses canonical bucket observations first, then the latest captured-time bucket per trade date. Intraday buckets remain available for state-path evidence, but they are not counted as separate trading days. Occupancy shares use canonical bucket observations as the denominator and are not confidence, forecast or performance statistics.

`tools/inspect_theme_dynamics.py` is read-only. It does not fetch AKShare, does not write CSV or SQLite and does not mutate `config/theme_taxonomy.json`.

`tools/inspect_observation_grain.py` is the focused grain audit CLI. It reports raw event counts, true duplicate event rows, collided buckets, extra events inside collided buckets, canonical observation counts and safe example metadata without printing raw market rows.

## Structural Regime Signatures

v3.12 consumes canonical bucket observations and creates a structural regime evidence path:

```text
canonical bucket observations
-> headline state
-> scope divergence table
-> member structural state
-> structural regime signature
-> regime episodes
-> observed transition trace
-> state-equivalent structural analysis
-> Multi-Day evidence panel / inspect_theme_regimes.py / brief section
```

The signature is semantic and deterministic:

```text
headline_state | scope_divergence_state | member_divergence_state
```

It does not use clustering, embeddings, model inference, weighted scores or hidden rules. The source fields already exist in the theme dynamics path, so the regime layer avoids a second implementation of scope or member divergence.

Episode boundaries are based on adjacent canonical observations. The project reports observation counts and first/last observed timestamps. It does not infer uninterrupted duration across overnight or missing-cache gaps.

State-equivalent analysis asks a narrow descriptive question: for the same headline state, how many structural signatures have been observed? The denominator for observed shares is the canonical observations inside that headline-state group. These shares are not future-oriented measures.

The CLI and Streamlit panel remain read-only: no AKShare calls, no CSV writes, no SQLite writes and no taxonomy mutation.

## Cross-Theme Semantic-Dynamic Relationship Evidence

v3.13 combines two existing governed evidence paths:

```text
theme_taxonomy.json
-> v3.9 cross-theme semantic overlap audit

canonical bucket observations
-> v3.12 structural regime signatures
-> exact aligned theme-pair observations
-> headline agreement / structural contrast / observed co-transition counts
```

The pairwise grain is:

```text
theme_pair × trade_date × captured_time_bucket × calculation_mode × source_mode × taxonomy_fingerprint
```

Only exact canonical bucket alignment is allowed. A pair observation is aligned only when both themes have canonical observations in the same trade date, captured-time bucket, calculation mode, source mode and taxonomy lineage. Missing buckets are counted as alignment gaps. The pipeline does not forward-fill, interpolate, nearest-match or compare raw physical events.

Headline evidence uses categorical state facts:

- exact-state agreement count/share
- same-sign observed count/share
- opposing-sign observed count/share
- state-pair contingency table

Structural evidence compares v3.12 categorical regime signatures:

- same signature count/share
- headline aligned but regime different count/share
- scope-structure agreement
- member-structure agreement

Co-transition evidence compares adjacent aligned canonical observations and reports observed simultaneous changes. The denominator is explicitly documented as aligned consecutive transition steps where at least one theme changed the measured dimension.

Semantic evidence comes from the existing v3.9 overlap audit: shared members, member union count, Jaccard overlap, shared strict representatives and overlap state. The relationship layer does not duplicate the Jaccard formula.

The output stays multi-dimensional by design. It does not create an opaque score, does not infer a mechanism and does not treat observed agreement as a forecast.

## Analytical Robustness and Specification Sensitivity

v3.14 adds a read-only robustness audit path:

```text
raw theme observation events
-> analytical specification identity
-> canonical materialization variants
-> theme / regime / relationship analysis
-> cross-specification comparison
-> evidence sufficiency and threshold-boundary evidence
```

The audit does not change production defaults. The default canonical policy remains `latest_valid_snapshot_in_bucket`, and default UI calculations continue to use the existing CSV-first / canonical-observation path.

The evaluated bucket widths are pre-declared as 1, 5 and 10 minutes. They are not selected from outcomes. For each width, the pipeline rebuilds raw theme observation events, applies deterministic canonical materialization and reuses existing theme/regime/relationship analysis functions.

Materialization-policy sensitivity is an offline audit. The supported variants are:

- `latest_valid_snapshot_in_bucket`
- `earliest_valid_snapshot_in_bucket`

The audit never averages cumulative "今日" snapshots, never sums snapshots and never averages ordinal state codes.

Calculation-scope sensitivity compares existing semantic scopes:

- strict representative
- representative
- breadth

The modes are displayed side by side. They are not ranked and no mode is selected because it produces a more convenient result.

Threshold-boundary proximity uses the existing `theme_pool` state thresholds. It records the nearest threshold and factual distance for each canonical observation where aggregate value is available. It does not mutate thresholds or describe a state as unreliable.

Date concentration is explicit. Each profile reports observations by date, represented trade-date count and max-date observation share. Pair evidence can also show per-date same-sign and exact-state observed shares while keeping the pooled denominator visible.
