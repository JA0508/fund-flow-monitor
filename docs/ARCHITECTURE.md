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
        +--> physical capture event inventory
        |         |
        |         v
        |   qualified acquisition frame coverage
        |
        v
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
- `src/provider_contracts.py`: semantic contract identity for provider/API facts and project-level normalization assumptions.
- `src/provider_registry.py`: read-only registry of primary and candidate provider contracts.
- `src/provider_comparability.py`: source comparability and continuity eligibility rules.
- `src/provider_network_diagnostics.py`: local read-only network path diagnostics without exposing proxy values.
- `src/concept_flow.py`: concept-flow helper logic.
- `src/transform.py`: raw AKShare/Eastmoney-style rows to the standard snapshot DataFrame.
- `src/data_contracts.py`: lightweight structural checks for snapshot and SAMPLE data.

The live path is optional but first-class for local real-data work. Current sector fund-flow collection uses AKShare's `stock_sector_fund_flow_rank` through a provider adapter, then normalizes rows with provenance fields such as provider, API name, fetched timestamp and `data_mode=REAL`. The adapter keeps the upstream boundary explicit: it records safe response metadata, builds a deterministic schema fingerprint, maps only known column variants and reports unsupported schemas as schema drift. If AKShare or a live fetch is unavailable, the app can still run with CACHE, HISTORY, SAMPLE, DEMO, or EMPTY states. The public Streamlit Cloud path should not depend on live fetch success.

## Provider Semantics And Continuity Layer

v3.15 adds a governed provider-semantics layer around the existing AKShare/Eastmoney real-data path. The primary contract is explicit:

```python
ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
```

The contract separates three kinds of information:

- factual provider/API evidence, such as function name, arguments, inspected AKShare source mapping and required source fields;
- project-level interpretation, such as treating each returned "今日" board ranking as an as-of-capture CSV snapshot;
- unknown semantics, which remain marked as `unknown` rather than filled in for completeness.

Candidate AKShare endpoints are registered as inspectable contracts, then classified with semantic dimensions such as metric family, time semantics, row grain, universe semantics, value semantics, unit and sign semantics. Similar function names or similar column names are not enough to make two sources equivalent.

Continuity eligibility is intentionally separate from runtime provider policy:

```text
provider contract
-> comparability classification
-> semantic eligibility
-> runtime policy
```

The default runtime policy remains `primary_only`. No automatic fallback is enabled, and no snapshot combines rows from two providers. If a future source is used for shadow comparison or fallback, the provider contract identity must remain visible in lineage and the history must not be silently presented as source-homogeneous.

## Analytical Continuity Segment Layer

v3.16 carries provider-contract identity into downstream analytical continuity. Physical snapshot IDs still describe where an observation came from, while `analytical_continuity_segment_id` describes whether observations are analytically compatible for canonical buckets, scope divergence, structural regime episodes, cross-theme pair alignment and robustness evidence.

The segment is derived from source mode, provider contract ID, provider contract fingerprint and resolution provenance. SAMPLE data uses a dedicated synthetic demo segment. REAL cache rows with explicit verified contracts, explicit ID only, inferred provider metadata or unknown lineage remain separate until their provenance is upgraded by a controlled ingestion path.

This layer does not change theme formulas, fetch data, write cache files or create a fallback provider. It is a guardrail that prevents provider-contract boundaries from being hidden inside later analytical outputs.

## Analytical Eligibility Layer

v3.17 separates two questions that were previously easy to confuse:

```text
Can the CSV history be read and replayed?
        |
        v
Is the observation qualified for a specific analytical workload?
```

Historical availability remains a coverage/readability statement. It can say that multiple REAL dates and snapshots exist. Qualified analytical readiness is stricter: REAL observations must carry explicit verified primary-provider contract identity before entering continuity-sensitive workloads such as structural regimes, cross-theme relationships and analytical robustness. Legacy REAL cache rows with unknown, inferred or explicit-ID-only provider-contract lineage remain auditable, but they are not counted as qualified analytical evidence.

SAMPLE synthetic rows are eligible only for SAMPLE demo analytics. This preserves the public demo path while keeping SAMPLE separate from real market history.

## Market-Session Date Boundary

v3.18 keeps capture-time semantics separate from market-session date eligibility:

- `captured_at` is the project fetch timestamp.
- `captured_time` is the project fetch clock time.
- `trade_date` in the current normalized provider path is derived from `captured_at` and acts as a project observation-session date.
- The AKShare / Eastmoney `indicator="今日"` path is treated as an as-of-capture ranking snapshot; it does not provide an explicit provider market-reference date that the project preserves.

The default bundled market-session date policy is conservative and offline. Without a declared calendar coverage source, REAL dates are `market_calendar_unverified`; a clock-window match such as `10:00` does not qualify a capture by itself. SAMPLE remains synthetic demo evidence and is not used to establish REAL market-session eligibility.

## Qualified Evidence Accumulation Layer

v3.18 adds a separate acquisition-evidence layer:

```text
normalized snapshot CSV
        |
        v
physical capture event
        |
        v
provider contract resolution + market-session date eligibility + acquisition eligibility
        |
        v
qualified acquisition event
        |
        v
predeclared acquisition frame cell
        |
        v
temporal coverage accumulation
```

Key module and tool:

- `src/evidence_accumulation.py`
- `tools/audit_evidence_accumulation.py`

The physical capture-event grain is one row per provider snapshot capture, identified by source mode, relative CSV path, trade date and captured time. It is not multiplied by sector rows, theme rows, calculation modes or analytical bucket variants.

The acquisition frame is derived from the configured collection sessions in `src/collection_policy.py`. Each trade date gets deterministic session cells, currently with a default 30-minute cell size. Cell IDs include the acquisition frame ID and session/cell boundaries. The boundary convention is `[start, end)`, with the final configured session endpoint included.

This layer keeps capture count separate from temporal coverage. The first qualified capture in a predeclared cell is marked as `new_cell_coverage`; later qualified captures in the same cell are marked as `additional_capture_in_existing_cell`. Qualified captures outside the configured sessions remain visible as `outside_acquisition_frame`, and unresolved or otherwise unqualified captures are excluded from qualified acquisition coverage.

This means `3 dates × 1 snapshot` can demonstrate historical availability, but it is not automatically the same as qualified multi-day acquisition coverage. The audit reports covered cells, missing cells and marginal contribution states explicitly. It does not fetch AKShare, write CSV files, write SQLite files, create a scheduler or change analytical materialization buckets.

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

## Theme Observation Evidence Layer

v3.8 adds factual calculation lineage for theme observations. It explains how normalized sector rows become a displayed theme state:

```text
normalized sector rows
        |
        v
theme taxonomy definition + fingerprint
        |
        v
canonical theme_pool matching and aggregation
        |
        v
theme evidence trace
        |
        v
Theme Radar / Multi-Day / Observation Brief provenance
```

The evidence path is attached to the canonical `theme_pool` calculation path. `build_theme_snapshot_with_trace()` reuses the same matching, selected-group and aggregation helpers as `build_theme_snapshot()`, then records the actual participating inputs. This avoids a separate reconstruction formula that could drift from the displayed result.

Theme observation evidence includes taxonomy fingerprint, theme-definition fingerprint, calculation mode, matched members, excluded members with factual reasons, aggregation method, aggregation inputs, aggregate value, threshold table, derived state, source mode and historical evidence dimensions.

Historical evidence is split into three factual dimensions:

- history span: no history, single date or multi-date
- intraday depth: no depth, single point per date, sparse intraday or dense intraday
- coverage consistency: unknown, uneven or consistent

This is analytical provenance. It is not model explainability, investment rationale, trading signal or prediction.

## Theme Taxonomy Calibration Layer

v3.9 adds a read-only semantic governance layer for `config/theme_taxonomy.json`. It keeps the legacy taxonomy schema compatible while exposing more explicit member metadata:

- `primary_sectors` are treated as `core` members and strict-representative candidates.
- `related_sectors` are treated as `related` members.
- Each member can carry mapping source, mapping method, rationale, aliases and strict-representative status.
- Alias resolution is deterministic and exact; ambiguous reused members are surfaced instead of silently selected.
- Cross-theme overlap is reported with shared members and Jaccard-style overlap ratios.
- Source-universe coverage is calculated separately for SAMPLE and REAL rows and uses the visible normalized source names as the denominator.

This layer does not rewrite the taxonomy, does not call AKShare, does not write CSV or SQLite, and does not merge SAMPLE and REAL evidence. It exists to make mapping provenance and calibration gaps visible for manual review.

## Theme Dynamics Layer

v3.10 adds a read-only observation fact layer on top of the existing theme evidence path. v3.11 hardens this into two explicit grains instead of treating every time-bucket collision as an ordinary duplicate.

Raw theme observation event grain:

```text
snapshot_event_id
theme_name
calculation_mode
source_mode
theme_definition_fingerprint
```

One raw event is one theme result calculated from one physical cached snapshot event under one calculation mode and one semantic theme definition. Exact `captured_at`, `captured_time`, trade date, provider metadata and file snapshot lineage remain attached, but the time bucket is not part of raw event identity.

Bucketed analytical observation grain:

```text
theme_name
trade_date
captured_time_bucket
calculation_mode
source_mode
taxonomy_fingerprint
theme_definition_fingerprint
```

One bucketed analytical observation is the canonical observation materialized for a time bucket. The default materialization policy is `latest_valid_snapshot_in_bucket`. The provider path used by the project is AKShare/Eastmoney's "今日" sector-flow snapshot, which the application treats as an as-of-capture cumulative snapshot. For that reason, the latest valid event inside a minute bucket is a better default than averaging, summing or blindly keeping all events for bucket-level dynamics. If all events fail contract checks, the latest event is retained only as an inspectable lineage row and is marked accordingly.

The layer builds raw theme observation events from existing CSV snapshots, analyzes bucket collisions, materializes one canonical bucket observation per analytical grain, then derives state transition traces, latest-per-date evolution, cross-scope divergence and member structural divergence. It reuses `build_theme_snapshot_with_trace()` so the matching, aggregation and state-threshold logic stays aligned with the displayed Theme Radar and Multi-Day panels.

This is not `drop_duplicates()` cleanup. Multiple valid captured events can share one minute bucket; they are bucket collisions with preserved contributing lineage, not automatically bad data. v3.11 separates true raw event duplicates, repeated file discovery, duplicated source rows and valid time-bucket collisions. State paths, occupancy shares and streaks now use canonical bucket observations as the denominator. Scope divergence compares modes aligned on the canonical bucket and exposes `alignment_status`, compared snapshot IDs and selected event IDs.

This layer is deliberately descriptive: it reads SAMPLE or local REAL cache, preserves source-mode and fingerprint boundaries, and does not call AKShare, write CSV, write SQLite or mutate the taxonomy. State paths and occupancy shares describe observed cached samples only; they are not forecasts, backtests or investment rationales.

## Structural Regime Signature Layer

v3.12 adds a deterministic structural signature layer on top of canonical bucket observations. The goal is to show when the same headline theme state hides different internal configurations.

One structural regime signature is composed from three already-governed dimensions:

```text
headline theme state
scope divergence state
member structural state
```

The human-readable signature stays visible, for example:

```text
弱流入|representative_positive_breadth_negative|balanced_divergence
```

The short `regime_signature_id` is only a deterministic identifier for lineage and table joins. It is not a score, rank or model output.

The layer reuses existing canonical logic:

- headline state comes from the canonical theme observation row
- scope structure comes from `build_scope_divergence_table()`
- member structure comes from the member divergence already attached by the theme trace path

It then segments contiguous observed canonical observations with the same signature into regime episodes, reports observed transition counts and identifies headline-preserving structural transitions. A headline-preserving structural transition means the displayed headline state remained the same while scope or member structure changed. It is a factual structural comparison, not a reversal signal or future-oriented measure.

State-equivalent structural analysis groups observations by headline state and reports how many structural signatures were observed under that same headline state. Observed shares use canonical observations within the selected headline-state group as the denominator.

REAL and SAMPLE, different theme-definition fingerprints and incompatible taxonomy fingerprints are not silently combined. When multiple lineages appear, the series is grouped or warning-labeled.

## Cross-Theme Relationship Evidence Layer

v3.13 adds a read-only cross-theme relationship layer. It answers a narrow descriptive question: when two governed themes are observed at the same canonical time bucket, how do their semantic overlap, headline state, structural regime signature and observed transitions compare?

The pairwise analytical grain is:

```text
theme_pair
trade_date
captured_time_bucket
calculation_mode
source_mode
taxonomy_fingerprint
```

`theme_pair` is deterministic and unordered, so `(AI算力/TMT, 半导体/芯片链)` and `(半导体/芯片链, AI算力/TMT)` are the same pair. Pair facts preserve both theme-definition fingerprints and both canonical observation IDs.

Alignment is exact:

- same trade date
- same captured-time bucket
- same calculation mode
- same source mode
- compatible taxonomy lineage
- canonical bucket observations only

There is no nearest-time matching, forward fill, interpolation or synthetic observation. Missing observations remain visible as alignment gaps.

The layer reports multiple separate evidence dimensions:

- semantic overlap from the v3.9 taxonomy overlap audit
- exact headline-state agreement
- same-sign observed share
- opposing-sign observed share
- structural-regime alignment from v3.12 signatures
- headline-aligned but regime-different observations
- observed simultaneous headline and structural changes

These dimensions are not collapsed into a single relationship score. Semantic overlap and observed dynamic alignment are kept side by side because they answer different questions. The topology summary is a deterministic edge-list/table, not a graph model.

This is not a mechanism engine, temporal-order model, trading signal, portfolio optimizer or correlation dashboard. Observed shares use aligned canonical pair observations as denominators and describe historical cache evidence only.

## Analytical Robustness Evidence Layer

v3.14 adds an analytical robustness layer on top of canonical observations, structural regime signatures and cross-theme relationship evidence. The purpose is to make the analytical specification visible instead of presenting one configuration as objective truth.

Each robustness result carries a deterministic analytical specification identity:

```text
captured_time_bucket_minutes
materialization_policy
calculation_mode
source_mode
taxonomy_fingerprint
canonical_observation_basis
state_mapping_identity
threshold_fingerprint
```

The default production specification remains:

```text
bucket=1m
policy=latest_valid_snapshot_in_bucket
mode=strict_representative
basis=canonical_bucket_observations
```

The robustness audit evaluates pre-declared variants rather than searching for a preferred outcome:

- bucket width: 1 / 5 / 10 minutes
- materialization policy audit: latest-valid and earliest-valid where defensible
- calculation scope: strict representative, representative and breadth as semantic scopes
- threshold proximity: distance from aggregate value to existing state thresholds

Evidence sufficiency is multidimensional. It reports canonical/aligned observations, represented trade dates, observations by date, max-date observation share, bucket count and alignment gaps. These fields are not collapsed into one score.

Cross-specification output is shown as factual ranges and disagreement counts. For example, a pair result can expose the range of same-sign observed share across evaluated specifications, plus the aligned-observation denominators that produced it. These ranges are not confidence intervals, probability estimates or model validation.

Topology/ranking views now include display sufficiency guardrails. Low-depth pairs remain inspectable in raw evidence, but ranked display rows show whether they meet configured minimum aligned observations and represented trade dates. This prevents an extreme `2/2` row from appearing as a top relationship without denominator context.

The layer is deliberately descriptive. It does not add p-values, relationship confidence, optimization, future-state prediction or investment-action language.

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
