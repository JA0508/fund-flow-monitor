# Validation notes

## Runtime checks

Run:

```bash
python tools/verify_runtime.py
```

The script reports the active project path, Python version, AKShare version, whether `stock_sector_fund_flow_rank` exists, current CSV path and row count, snapshot count, latest captured time, latest inflow/outflow leaders, CSV snapshot catalog, DEMO contamination check, unit sanity check, and whether the current cache can build `strict_representative`, `representative`, and `breadth` fund observation theme snapshots.

## v3.13 Cross-Theme Relationship Evidence Checks

Run:

```bash
python tools/quality_gate.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/release_check.py
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python tools/smoke_check.py
python tools/verify_runtime.py
python tools/inspect_theme_relationships.py --source-mode SAMPLE --mode strict_representative --json
python tools/inspect_theme_relationships.py --source-mode SAMPLE --mode strict_representative --top-semantic-overlap --limit 10
python tools/inspect_theme_relationships.py --source-mode SAMPLE --mode strict_representative --top-state-alignment --limit 10
python tools/inspect_theme_relationships.py --source-mode SAMPLE --mode strict_representative --top-structural-contrast --limit 10
python tools/inspect_theme_relationships.py --source-mode SAMPLE --mode strict_representative --pair "AI算力/TMT::半导体/芯片链" --co-transitions
```

Required checks:

- `APP_VERSION` is `v3.13`.
- `CHANGELOG.md` contains a `v3.13` entry.
- `src/theme_relationships.py` exists and is importable.
- `tools/inspect_theme_relationships.py` exists and can inspect SAMPLE without network or writes.
- Pair grain is `theme_pair × trade_date × captured_time_bucket × calculation_mode × source_mode × taxonomy_fingerprint`.
- Theme pairs are deterministic unordered pairs; `(A, B)` and `(B, A)` are the same pair.
- Pair alignment uses canonical bucket observations only, with exact `trade_date` and `captured_time_bucket` matches; no nearest-time match, forward fill or interpolation is allowed.
- Alignment gaps remain visible in summaries instead of being silently dropped.
- Exact headline-state agreement and same-sign observed share are reported separately with explicit denominators.
- Structural-regime alignment reuses v3.12 signatures and exposes headline-aligned but regime-different observations.
- Semantic overlap reuses v3.9 taxonomy overlap evidence and remains separate from observed dynamic alignment.
- Co-transition evidence is reported as observed counts/shares on aligned historical steps, not as future-oriented relationship evidence.
- No overall relationship score, mechanism claim, temporal-order model, trading signal or investment recommendation is introduced.
- SAMPLE and REAL source modes remain explicitly separated.

## v3.7 Historical Coverage and Replay Provenance Checks

Run:

```bash
python tools/quality_gate.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/release_check.py
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python tools/smoke_check.py
python tools/verify_runtime.py
python tools/inspect_history_evidence.py --source-mode REAL
python tools/inspect_history_evidence.py --data-dir sample_data/ticks --source-mode SAMPLE --matrix
```

Optional live provider sanity check:

```bash
python tools/probe_akshare.py --json
```

Required checks:

- `APP_VERSION` is `v3.7`.
- `CHANGELOG.md` contains a `v3.7` entry.
- `src/history_evidence.py` exists and is importable.
- `tools/inspect_history_evidence.py` exists and can inspect REAL or SAMPLE CSV directories without network or writes.
- Snapshot evidence records include deterministic `snapshot_id`, file hash, relative path, trade date, captured_time coverage, provider/API metadata when present, schema fingerprint and data contract status.
- Coverage matrix buckets captured_time by minute by default and reports counts per `trade_date` x `captured_time_bucket`.
- Readiness states are limited to evidence coverage labels such as `no_real_history`, `single_snapshot`, `single_day_intraday`, `limited_multi_day` and `multi_day_ready`.
- Replay evidence for a selected date reports snapshot IDs, captured_time range, provider/API counts, schema consistency and contract pass count without exposing row-level data.
- Streamlit multi-day and data explanation tabs show Historical Evidence as a read-only panel and do not replace existing multi-day trend calculations.
- SAMPLE evidence must stay labeled as `SAMPLE` / synthetic demo data and must not be described as real market history.
- Tests, smoke checks, runtime verification, cloud preflight and release checks must not call live AKShare or require real `data/ticks`.
- No tracked real `data/ticks/*.csv`, collector logs, provider diagnostics, SQLite files, secrets or virtual environments are allowed.
- Historical evidence must not include performance-analysis, prediction or advice language.

## v3.6 Bounded Real-data Ingestion Orchestration Checks

Run:

```bash
python tools/quality_gate.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/release_check.py
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python tools/smoke_check.py
python tools/verify_runtime.py
```

Optional local operations checks:

```bash
python tools/collect_real_snapshot.py --no-network
python tools/run_collection_session.py --max-runs 3 --interval-seconds 0 --dry-run --no-log --ignore-session
python tools/probe_akshare.py --json
```

Required checks:

- `APP_VERSION` is `v3.6`.
- `CHANGELOG.md` contains a `v3.6` entry.
- `src/collection_policy.py` exists and is importable.
- `src/ingestion_metrics.py` exists and is importable.
- `tools/run_collection_session.py` exists and exposes a finite runner CLI.
- Collection policy states include `eligible`, `outside_session`, `too_soon_since_success`, `max_attempts_reached` and `disabled`.
- `run_collection_session.py` uses a bounded `for` loop with `--max-runs`; it must not run forever.
- `run_collection_session.py --dry-run --no-log --ignore-session` must not write `data/ticks` or collector logs.
- Ingestion metrics read `data/logs/collector_runs.jsonl` if present and tolerate missing or malformed logs.
- Success-rate denominator excludes `dry_run` and `no_network`, and labels the denominator as write-intent runs.
- Cache coverage labels include `no_real_data`, `single_snapshot`, `limited_intraday_coverage` and `usable_intraday_coverage`.
- `smoke_check.py`, `verify_runtime.py`, `release_check.py` and `cloud_preflight.py` must not call live AKShare.
- No tracked real `data/ticks/*.csv`, collector logs, provider diagnostics, SQLite files, secrets or virtual environments are allowed.
- SAMPLE fallback remains public demo data and must not be used to mask failed real-data ingestion.

## v3.5 AKShare Provider Boundary Checks

Run:

```bash
python tools/quality_gate.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/release_check.py
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python tools/smoke_check.py
python tools/verify_runtime.py
```

Optional live-data diagnostics:

```bash
python tools/probe_akshare.py
python tools/probe_akshare.py --json
python tools/collect_real_snapshot.py --no-network
python tools/collect_real_snapshot.py --dry-run --no-log
```

Required checks:

- `APP_VERSION` is `v3.5`.
- `CHANGELOG.md` contains a `v3.5` entry.
- `src/providers/akshare_sector_flow.py` exists and is importable.
- `tools/probe_akshare.py` exists and does not write `data/ticks`.
- The real sector-flow path uses `ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")`.
- Known AKShare column variants are mapped through explicit aliases.
- Unknown provider schemas fail as `schema_drift`.
- Ambiguous provider column mappings fail clearly and do not silently choose a column.
- Empty provider DataFrames are classified as `empty_response`.
- Upstream JSON parse failures are classified as `provider_parse_error` where practical.
- Project-owned normalization failures are classified as `normalization_error`.
- Real snapshot contract failures remain separate as `contract_error`.
- Schema fingerprints are deterministic and do not include full raw market rows.
- Retry is bounded and only applies to network/timeout failures.
- Unit tests mock provider responses and do not require live AKShare.
- `quality_gate.py`, `smoke_check.py`, `verify_runtime.py`, `release_check.py`, and `cloud_preflight.py` must not call live AKShare.
- `data/ticks/*.csv`, `data/logs/`, provider diagnostics, SQLite files, secrets and virtual environments must remain ignored.
- SAMPLE fallback remains available and is not treated as real market data.

## v3.4 Real Cache Catalog and Freshness Evidence Checks

Run:

```bash
python tools/quality_gate.py
python tools/release_check.py
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
```

Optional live-data checks:

```bash
python tools/collect_real_snapshot.py --no-network
python tools/collect_real_snapshot.py --dry-run --no-log
```

Required checks:

- `APP_VERSION` is `v3.4`.
- `CHANGELOG.md` contains a `v3.4` entry.
- `build_real_cache_summary` reports real cache existence, snapshot count, date count, available dates, latest path/date/time, modified time, empty/malformed/valid file counts, staleness status and warnings.
- Collector audit-log reader handles missing logs, valid JSONL logs and malformed lines without writing files.
- `数据说明` tab shows compact current data-status evidence, real cache coverage/freshness and latest collector run status.
- `smoke_check.py` and `verify_runtime.py` report real cache evidence and collector audit-log visibility without requiring real cache or live AKShare in CI.
- Missing real cache and missing collector logs remain acceptable in public SAMPLE demo / Streamlit Cloud.
- No real `data/ticks/*.csv`, collector logs, SQLite, secrets, virtualenv, `.DS_Store` or cache files are staged or tracked.

## v3.3 Real Collector Audit Workflow Checks

Run:

```bash
python tools/quality_gate.py
python tools/release_check.py
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
python tools/collect_real_snapshot.py --no-network
python tools/collect_real_snapshot.py --dry-run --no-log
```

Required checks:

- `APP_VERSION` is `v3.3`.
- `CHANGELOG.md` contains a `v3.3` entry.
- `collect_real_snapshot.py --no-network` must not call AKShare and must not write `data/ticks`.
- `collect_real_snapshot.py --dry-run` may call AKShare but must not write `data/ticks`.
- Collector output includes `status`, row count, trade date, captured time, provider/API, contract label, log status and error category where applicable.
- Collector statuses include success, dry-run, no-network, fetch error, empty fetch, contract error, duplicate skip and write error cases.
- By default, collector runs append JSONL audit records under `data/logs/collector_runs.jsonl`; `--no-log` disables this.
- `data/logs/` and `logs/` are ignored by Git.
- Tests use mocked fetches and do not require live AKShare.
- No real `data/ticks/*.csv`, collector logs, SQLite, secrets, virtualenv, `.DS_Store` or cache files are staged or tracked.

## v3.2 Real Data Ingestion and Cache Quality Checks

Run:

```bash
python tools/quality_gate.py
python tools/release_check.py
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
```

Optional live-data checks:

```bash
python tools/collect_real_snapshot.py --dry-run
python tools/probe_akshare.py
```

Required checks:

- `APP_VERSION` is `v3.2`.
- `CHANGELOG.md` contains a `v3.2` entry.
- `docs/REAL_DATA_INGESTION.md` exists.
- `tools/collect_real_snapshot.py` exists and delegates to the existing one-shot collector.
- Real AKShare normalization includes practical provenance fields such as `data_mode=REAL`, provider, API name, fetched timestamp and rank value when available.
- Real snapshot data contract rejects SAMPLE / DEMO markers without forcing SAMPLE-specific fields on real cache.
- `collect_real_snapshot.py --dry-run` must not write `data/ticks`.
- The Streamlit data explanation tab shows compact real cache freshness/provenance when local real cache exists, and remains readable when it does not.
- SAMPLE fallback remains intact and is still clearly marked as synthetic demo data.
- Tests do not require live network access.
- No real `data/ticks/*.csv`, SQLite, secrets, virtualenv, `.DS_Store` or cache files are staged or tracked.

## v3.1 CI and Operational Quality Hardening Checks

Run:

```bash
python tools/quality_gate.py
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python tools/release_check.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
```

Required checks:

- `APP_VERSION` is `v3.1`.
- `CHANGELOG.md` contains a `v3.1` entry.
- `.github/workflows/ci.yml` uses clean-runner commands, not `.venv/bin/python`.
- CI installs `requirements.txt` and runs pytest, compileall, release_check, cloud_preflight and public demo preflight.
- `tools/quality_gate.py` exists and can run the local pre-push quality gate.
- `tests/test_quality_gate.py` passes.
- `docs/OPERATIONS.md` exists and explains local run, quality gate, CI, Streamlit Cloud, SAMPLE public mode, troubleshooting and forbidden files.
- Data contracts remain lightweight and do not force SAMPLE markers on non-SAMPLE local/cache data.
- Public demo behavior remains SAMPLE-first when no local cache is available.
- No real CSV, SQLite, secrets, virtualenv, `.DS_Store` or cache files are staged or tracked.

## v3.0 Engineering Architecture Hardening Checks

Run:

```bash
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python tools/release_check.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
```

Required checks:

- `APP_VERSION` is `v3.0`.
- `CHANGELOG.md` contains a `v3.0` entry.
- `docs/ARCHITECTURE.md` exists and explains module boundaries without claiming production financial-platform readiness.
- `docs/DATA_FLOW.md` exists and explains `LIVE / CACHE / HISTORY / SAMPLE / DEMO / EMPTY`.
- `src/data_contracts.py` exists.
- `tests/test_data_contracts.py` passes.
- `release_check.py` reports SAMPLE data contract status.
- `cloud_preflight.py` checks SAMPLE data contract status and architecture/data-flow docs.
- `smoke_check.py` and `verify_runtime.py` report SAMPLE data contract readiness.
- SAMPLE remains synthetic demo data and is not described as real market data.
- No backend service, account login, brokerage connection, trading action, or prediction wording is introduced.
- No real CSV, SQLite, secrets, virtualenv, or cache files are staged or tracked.

## v2.9 Public Release Final Audit Checks

Run:

```bash
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python tools/release_check.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
git status --short
git ls-files | grep -E "(.env|.venv|secrets.toml|data/ticks|.sqlite|.db)" || true
```

Required checks:

- `APP_VERSION` is `v2.9`.
- `CHANGELOG.md` contains a `v2.9` entry.
- `docs/PUBLIC_RELEASE_AUDIT.md` exists and contains go/no-go criteria.
- `docs/PORTFOLIO_PRESENTATION.md`, `docs/INTERVIEW_TALKING_POINTS.md`, and `docs/RESUME_SNIPPETS.md` exist.
- `release_check.py` reports no tracked forbidden files.
- `release_check.py` confirms APP_VERSION / CHANGELOG consistency.
- Public demo and SAMPLE boundaries remain clear.
- No real CSV, SQLite, secrets, virtualenv, or cache files are staged or tracked.

## v2.8 Public Portfolio Presentation Checks

Run:

```bash
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python tools/release_check.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
```

Required checks:

- First screen contains a compact demo guide explaining the main tabs.
- Public/SAMPLE mode remains clearly marked as synthetic demo data and not real market data.
- v2.7 first-visit SAMPLE fallback remains intact.
- README contains a short “What to look at in the demo” path.
- PROJECT_BRIEF describes v2.8 as presentation polish, not a new data feature.
- Page and docs do not introduce trading actions, fund recommendations, or future prediction wording.
- No real `data/ticks`, SQLite, secrets, or virtualenv files appear in git status.

## v2.7 Public Deployment First-visit Checks

Run:

```bash
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
```

Required checks:

- `src/runtime_profile.py` keeps local/cache default when real `data/ticks` CSV exists.
- If real cache is absent but `sample_data/ticks` exists, runtime defaults to `SAMPLE`.
- First-visit SAMPLE fallback defaults to `作品集演示模式`.
- Sidebar notice explains SAMPLE is synthetic demo data and not real market data.
- Users can still manually switch to real/cache mode.
- Real/cache mode with no cache still shows `EMPTY` / warning behavior.
- SAMPLE mode does not trigger AKShare and does not write `data/ticks`.
- Page and docs contain no trading advice or prediction wording.

## v2.6 Public Demo Runtime Checks

Run:

```bash
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python tools/release_check.py
python tools/export_sample_brief.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
```

Required checks:

- `src/runtime_profile.py` exists.
- `tools/cloud_preflight.py` exists.
- `tests/test_runtime_profile.py` passes.
- `tests/test_cloud_preflight.py` passes.
- `FUND_FLOW_PUBLIC_DEMO=1` makes runtime profile default to `SAMPLE`.
- Public demo profile defaults to `作品集演示模式`.
- Public demo profile does not auto-write `data/ticks`.
- Public demo profile does not auto-write `data/warehouse`.
- No warehouse: app still runs and shows manual rebuild guidance.
- `cloud_preflight.py` does not access network.
- `cloud_preflight.py` does not write `data/ticks` or `data/warehouse`.
- README contains `Public Demo Runtime Profile` and `Cloud Preflight`.
- `docs/RELEASE_CHECKLIST.md` contains public demo runtime checks.
- Page and docs keep SAMPLE clearly marked as synthetic demo data and not real market data.

## v2.5 Public Portfolio Release Checks

Run:

```bash
python tools/release_check.py
python tools/export_sample_brief.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
```

Required checks:

- `src/release_readiness.py` exists.
- `tools/release_check.py` exists.
- `tests/test_release_readiness.py` passes.
- README contains a public portfolio walkthrough, SAMPLE boundary notes and release check commands.
- README links point to existing files and do not reference missing screenshots.
- `docs/demo_briefs/sample_observation_brief.md` remains readable and clearly marked as SAMPLE.
- `docs/screenshots/SCREENSHOT_GUIDE.md` contains the recommended screenshot set.
- `docs/RELEASE_CHECKLIST.md` includes `release_check.py`.
- `tools/release_check.py` does not access network and does not write `data/ticks` or `data/warehouse`.
- Page and docs contain no trading advice or prediction wording.

## v2.4 Theme History Brief Checks

Run:

```bash
python tools/export_sample_brief.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
```

Required checks:

- `src/theme_history_brief.py` exists.
- `tests/test_theme_history_brief.py` passes.
- The `观察简报` tab contains a `包含 Warehouse 主题历史摘要` switch.
- No warehouse: observation brief still renders and does not rebuild warehouse.
- SAMPLE warehouse: observation brief can include a SAMPLE theme history section.
- SAMPLE theme history section clearly marks synthetic demo data and not real market data.
- `tools/export_sample_brief.py` includes theme history by default, does not read `data/ticks`, and does not write default `data/warehouse`.
- `docs/demo_briefs/sample_observation_brief.md` contains `主题历史观察摘要`.
- Demo brief contains no local absolute paths, trading advice or prediction wording.

## v2.3 Theme History Visualization Checks

Run:

```bash
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
python tools/rebuild_local_warehouse.py --include-sample --clear
```

Required checks:

- `src/theme_history_viz.py` exists.
- `tests/test_theme_history_viz.py` passes.
- The `多日趋势` tab contains a `主题历史图表` area inside `Warehouse 主题历史观察（只读）`.
- No warehouse: the app still runs and does not render empty chart shells.
- SAMPLE warehouse: line chart, heatmap, latest bar chart and compact status timeline are available.
- SAMPLE chart copy clearly marks synthetic demo data and not real market data.
- `chart_option`, `top_n` and optional selected themes controls work without errors.
- Chart rendering does not replace existing CSV multi-day trend logic.
- The chart panel does not rebuild warehouse, write SQLite, write CSV or access network.
- Page and docs contain no trading advice or prediction wording.

## v2.2 Theme History Checks

Run:

```bash
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
python tools/rebuild_local_warehouse.py --include-sample --clear
```

Required checks:

- `src/theme_history.py` exists.
- `tests/test_theme_history.py` passes.
- The app still runs when no warehouse exists.
- With SAMPLE warehouse, `多日趋势` tab shows `Warehouse 主题历史观察（只读）`.
- SAMPLE-only theme history is explained as synthetic demo data, not a severe error.
- LOCAL not imported is shown as a readable state.
- Theme history does not replace the existing CSV multi-day trend logic.
- Theme history panel does not rebuild warehouse, write SQLite, write CSV or access network.
- Page and docs contain no trading advice or prediction wording.

## v2.1 Warehouse Explorer Checks

Run:

```bash
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
python tools/rebuild_local_warehouse.py --include-sample --clear
```

Required checks:

- `src/warehouse_explorer.py` exists.
- `tests/test_warehouse_explorer.py` passes.
- The app still runs when `data/warehouse/fund_flow.sqlite` does not exist.
- `数据说明` tab contains `Warehouse Explorer（只读）`.
- Explorer can show source_type, date, captured_time and sector sample previews when a SAMPLE warehouse exists.
- Explorer does not automatically rebuild warehouse.
- Explorer does not write SQLite, does not write CSV and does not access network.
- CSV-Warehouse consistency audit is visible and explains SAMPLE-only / LOCAL-not-imported states.
- SAMPLE-only warehouse is not treated as a severe app error.
- Page and docs contain no trading advice or prediction wording.

## v2.0 Local SQLite Warehouse Checks

Run:

```bash
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
python tools/rebuild_local_warehouse.py --include-sample --dry-run
```

Required checks:

- `src/local_warehouse.py` exists.
- `tools/rebuild_local_warehouse.py` exists.
- `data/warehouse/` is ignored by Git.
- `*.sqlite`, `*.sqlite3`, and `*.db` are ignored by Git.
- A temporary SQLite warehouse can be initialized.
- `sample_data/ticks` can be imported into a temporary warehouse.
- `--dry-run` does not create SQLite files.
- Default rebuild behavior does not import `data/ticks` unless `--include-local` is explicitly passed.
- The app still runs without a warehouse file.
- `数据说明` tab contains `本地 SQLite Warehouse（可重建索引）`.
- The Streamlit page does not automatically rebuild the warehouse.
- `tools/verify_runtime.py` does not access network and does not write the default `data/warehouse`.
- Tests do not access network, do not read real `data/ticks`, and do not write the default warehouse path.

Manual checks:

- Run `python tools/rebuild_local_warehouse.py --include-sample`.
- Confirm `data/warehouse/fund_flow.sqlite` is created locally but does not appear in `git status`.
- Confirm the data explanation tab shows warehouse file/row counts and available SAMPLE dates.
- Confirm CSV remains the primary app data path and no core tab requires SQLite to render.
- Confirm warehouse text describes a rebuildable local index, not an investment conclusion.

## v1.9 Observation Brief Release Checks

Run:

```bash
python tools/export_sample_brief.py
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
```

Required checks:

- `src/brief_templates.py` exists.
- `tools/export_sample_brief.py` exists.
- `docs/demo_briefs/README.md` exists.
- `docs/demo_briefs/sample_observation_brief.md` exists.
- `docs/RELEASE_CHECKLIST.md` exists.
- Observation brief tab contains template selection.
- Standard brief and portfolio demo brief can be generated.
- SAMPLE portfolio brief explicitly says it is based on synthetic demo data.
- Demo brief does not contain action-oriented investment wording.
- Demo brief does not contain local absolute paths.
- `tools/export_sample_brief.py` does not access network.
- `tools/export_sample_brief.py` does not read or write `data/ticks`.
- README links to the demo brief and release checklist point to real files.
- Page and documentation do not contain prediction or trading-action wording.

## v1.8 Portfolio Presentation Checks

Run:

```bash
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
```

Required checks:

- `src/presentation.py` exists.
- Sidebar contains `展示模式` with `标准模式` and `作品集演示模式`.
- Standard mode keeps the v1.7 experience.
- Portfolio mode reduces debug noise but does not change calculations.
- Portfolio mode does not trigger AKShare and does not write CSV.
- `SAMPLE` and `DEMO` non-real-data notices remain visible.
- Unified status badge supports `LIVE / CACHE / HISTORY / SAMPLE / DEMO / EMPTY`.
- `数据说明` tab includes demo walkthrough and screenshot checklist.
- `docs/screenshots/SCREENSHOT_GUIDE.md` exists.
- README includes Demo Walkthrough and Portfolio Presentation Mode.
- README must not contain broken Markdown image links.
- Page and documentation must not contain trading actions or future-direction predictions.

Manual page checks:

- Switch `数据来源模式` to SAMPLE and `展示模式` to `作品集演示模式`.
- Browse `实时曲线`, `主题雷达`, `日内热点`, `多日趋势`, `持仓相关池`, `观察简报`, `排行榜`, and `数据说明`.
- Confirm `SAMPLE` is always described as synthetic demo data and not real market data.
- Confirm long CSV/debug details are available through expanders rather than removed.

## v1.7 Snapshot Governance Checks

Run:

```bash
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
python tools/collect_market_snapshot.py --no-network
```

Required checks:

- `src/snapshot_quality.py` exists.
- `tools/collect_market_snapshot.py` exists.
- `tests/test_snapshot_quality.py` and `tests/test_collect_market_snapshot.py` pass without network access.
- `tools/smoke_check.py` reports snapshot quality local/sample file counts.
- `tools/verify_runtime.py` reports `snapshot_quality_report_label`, local/sample file counts, sample catalog row count, and `snapshot_quality_forbidden_hits`.
- `tools/collect_market_snapshot.py --no-network` does not access AKShare and does not write files.
- `tools/collect_market_snapshot.py --dry-run` may attempt a real fetch, but must not write `data/ticks`; if AKShare fails, it should print a clear error and not generate fake data.
- The Streamlit page must not run the collection script automatically.
- The collection script must not run as a background service, timer, or loop.
- The collection script must not write to `sample_data/ticks`.
- `data/ticks/*.csv` remains ignored by Git.
- `sample_data/ticks/*.csv` remains commit-ready.

Manual page checks:

- `数据说明` tab contains `CSV 快照数据质量`.
- It shows local real cache summary and SAMPLE sample data summary.
- It shows local CSV file quality table and SAMPLE CSV file quality table.
- Missing `data/ticks` or an empty local cache should not crash the app.
- Bad CSV or missing fields should show warning/error in an expander rather than breaking the page.
- The first-run prompt may show:

```bash
python tools/collect_market_snapshot.py --dry-run
python tools/collect_market_snapshot.py
```

but it must not execute these commands from Streamlit.

Text boundary checks:

- Data quality text only describes file/field quality.
- It must not describe investment conclusions, trading actions, or future price direction.
- SAMPLE and DEMO still must not be written into `data/ticks`.

For v0.5 it also checks whether the app can build:

- `theme_radar_snapshot`
- `market_temperature`
- configured `watchlist.json`
- watchlist theme matches
- strict-vs-breadth divergence rows

DEMO contamination detection only checks mode-like fields: `source`, `sector_type`, `mode`, and `data_mode`. It intentionally does not inspect `sector_name`, because real Eastmoney sector names can contain words such as `模拟芯片设计`.

## Fund observation pool

The fund observation pool is not a simple sum of every related board.

- `strict_representative / 严格代表口径`: uses exact matches from primary sectors only. If no exact primary sector exists, it may use exact related sectors as a clearly marked replacement. This is the default and most conservative mode.
- `representative / 代表口径`: uses exact primary sectors first, then falls back to primary contains, exact related sectors, or related contains. This lowers duplicate-counting risk compared with broad aggregation while keeping more coverage.
- `breadth / 广度观察`: uses primary and related sectors together to observe theme heat. The number can include overlapping sector definitions and should not be read as strict net inflow.

Current theme mapping is a lightweight rule layer. Later versions should calibrate it with fund holdings, ETF constituents, and a formal industry taxonomy.

Theme status labels such as `强流入` and `强流出` are fund-flow state tags only. They are not trading signals or investment advice.

## v0.5 Radar Layer

The radar layer turns the latest theme snapshot into product-facing summaries:

- 今日资金温度: scores theme statuses with `强流入=+2`, `弱流入=+1`, `分歧/中性=0`, `弱流出=-1`, `强流出=-2`.
- 关注主题雷达: filters the current theme snapshot by `config/watchlist.json`.
- 核心/广度分歧提示: compares `strict_representative` with `breadth` to identify whether core and related sectors move together or diverge.

These summaries describe observed fund-flow state only. They do not predict future prices, do not include trading functions, and do not provide investment advice.

The project is for learning, research, and visualization only. It is not investment advice.

## v0.6 Delivery Checks

Run the full local validation set:

```bash
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
```

Manual Streamlit checks:

- Page has four tabs: `实时曲线`, `主题雷达`, `排行榜`, `数据说明`.
- `实时曲线` contains the compact status bar, error/cache/demo notice, and main Plotly curve.
- `主题雷达` contains 今日资金温度, 关注主题雷达, and 核心/广度分歧提示.
- `排行榜` contains 今日净流入榜 and 今日净流出榜; inflow rows must be positive only and outflow rows must be negative only.
- `数据说明` contains the data trust panel, `LIVE / CACHE / HISTORY / SAMPLE / DEMO / EMPTY` explanation, theme mode explanation, watchlist instructions, and disclaimer.
- Page footer shows `养基宝主题资金流雷达 · v0.7 · Streamlit MVP`.
- No Streamlit default white dataframe should appear in the main dashboard.
- No trading or prediction wording should appear in user-facing text.

Project documentation checks:

- `README.md` is GitHub-ready and includes overview, features, screenshots placeholder, architecture, data flow, theme modes, watchlist, quick start, validation, limitations, and roadmap.
- `CHANGELOG.md` records v0.1 through v0.7.
- `ROADMAP.md` follows the long-term direction: Streamlit MVP, low-frequency concept flow, fund/ETF holdings mapping, holding-related pool, intraday hotspot pool, then FastAPI + React + ECharts.
- `PROJECT_BRIEF.md` can be used as a portfolio project description.

`tools/smoke_check.py` is intentionally offline. It does not call AKShare; it checks Python version, key imports, project files, watchlist loading, and local CSV summary.

DEMO safety check remains required:

- Enable DEMO mode.
- Confirm `data/ticks/sector_flow_YYYY-MM-DD.csv` row count does not increase.
- Confirm `tools/verify_runtime.py` reports no DEMO contamination in real CSV.

Forbidden wording check:

- The app may state that it does not provide trading functions or investment advice.
- User-facing analysis should not contain action-oriented trading suggestions.

## v0.7 Concept Assistance Checks

Concept fund-flow is a low-frequency auxiliary source:

- Sidebar has `概念资金流辅助` toggle.
- When enabled, the page shows `刷新概念资金流`.
- Concept data should refresh only when the button is clicked, the concept cache is empty, or the cache is older than 5 minutes.
- The app must not fetch concept fund-flow every 30 seconds.
- Concept fetch failures must not block the industry fund-flow chart or ranking.
- Concept status should be one of `CONCEPT_LIVE`, `CONCEPT_CACHE`, `CONCEPT_EMPTY`, or `CONCEPT_ERROR`.
- `主题雷达` tab should show `相关概念热度` when concept assistance is enabled.
- `排行榜` must not mix concept hotspots into the main inflow/outflow ranking.
- `数据说明` must state that industry and concept fund-flow are not directly added together.

Validation scripts:

```bash
python tools/probe_concept_flow.py
python tools/verify_runtime.py
```

`verify_runtime.py` should report:

- industry rows / unique captured_time
- concept rows / unique captured_time
- whether concept hotspots can be built
- whether theme concept summary can be built

If no concept cache exists, this is acceptable. The script should print:

```text
暂无概念资金流缓存，可通过页面手动刷新生成。
```

## v0.8 Holding-Related Pool Checks

The holding-related pool is based on local manual theme configuration only:

- Page has a `持仓相关池` tab.
- `config/fund_profiles.json` exists and uses `DEMO-` fund codes in the sample profile.
- `src/fund_profiles.py` can load missing or damaged config files without crashing.
- The tab shows a clear note: manual configuration, not real holdings, no account connection, no investment advice.
- The tab shows profile overview, fund summary cards, and a dark theme exposure table.
- `verify_runtime.py` reports:
  - fund profile name
  - fund count
  - warning count
  - exposure rows
  - holding related rows
  - fund summary Top 3
- Missing theme names in `fund_profiles.json` should show warnings, not crash the page.
- The holding impact score is derived from configured theme weight and current theme status only.
- The holding-related pool must not be described as real holdings or fund NAV prediction.

Forbidden wording check:

- User-facing holding text must not include action-oriented words such as `买入`, `卖出`, `加仓`, `减仓`, `抄底`, `逃顶`, `推荐买`, `建议买`, `建仓`, or `清仓`.

## v0.9 Intraday Hotspot Checks

The intraday hotspot pool uses local CSV snapshots only:

- Page has a `日内热点` tab.
- The tab explains that it uses same-day CSV snapshots and only describes already observed intraday fund-flow changes.
- It must not call new AKShare endpoints.
- If `captured_time` count is below 2, the tab shows a clear insufficient snapshot message and does not crash.
- If enough snapshots exist, the tab shows:
  - overview cards
  - 流入/修复主题
  - 日内改善主题
  - 承压/走弱主题
  - 日内变化明细 dark table
- `verify_runtime.py` reports:
  - whether `theme_intraday_history` can be built
  - `snapshot_count`
  - whether intraday metrics can be built
  - whether hotspot pool can be built
  - hotspot summary label and Top 3 hotspot themes
- Concept fund-flow failure must not affect intraday hotspots.
- DEMO still must not write to real CSV.

Forbidden wording check:

- Intraday hotspot text must not include action-oriented words such as `买入`, `卖出`, `加仓`, `减仓`, `抄底`, `逃顶`, `推荐买`, `建议买`, `建仓`, or `清仓`.
- Hotspot explanations must not describe future price or fund NAV prediction.

## v1.0 Historical Replay Checks

Historical replay uses local CSV snapshots only:

- Sidebar has `数据日期 / 历史回放` controls.
- User can choose `自动使用最新缓存` or `选择历史日期`.
- Historical date options should include snapshot date, captured_time count, and quality label.
- Selecting a historical date sets the top status to `HISTORY`.
- `HISTORY` mode must not call AKShare.
- `HISTORY` mode must not write to CSV.
- `HISTORY` mode should drive all tabs from the selected date:
  - 实时曲线
  - 主题雷达
  - 日内热点
  - 持仓相关池
  - 排行榜
- If selected date has multiple `captured_time`, 日内热点 should show cards and a dark detail table.
- If selected date has only one `captured_time`, 日内热点 should show the insufficient snapshot message and not crash.
- 排行榜 should use the selected date's latest `captured_time`.
- 持仓相关池 should use the selected date's theme radar result and must not describe real holdings or returns.
- 数据说明 tab should include:
  - `LIVE / CACHE / HISTORY / SAMPLE / DEMO / EMPTY` explanation
  - selected snapshot date
  - CSV snapshot catalog
  - quality label and quality reason
- If no CSV exists, app should show `EMPTY` and remain usable.
- DEMO still must not write to real CSV.

`verify_runtime.py` should report:

- whether snapshot catalog can be built
- available snapshot dates
- best replay date
- best replay captured_time_count
- best replay quality_label
- whether selected historical date can build theme radar, holding related pool, ranking, and intraday hotspot pool when enough snapshots exist

`tools/smoke_check.py` should report the snapshot catalog date count without network access.

## v1.1 Multi-day Trend Checks

The multi-day trend layer uses local CSV snapshot dates only:

- Page has a `多日趋势` tab.
- Sidebar has a clearly named `多日趋势口径` selector.
- The tab explains that it uses multiple cached CSV dates and only describes saved historical fund-flow states.
- It must not call new AKShare endpoints.
- It must not use 5-day, 10-day, regional, or concept fund-flow APIs.
- It must not write CSV.
- It should be independent from `selected_snapshot_date`; selecting a single history date should not restrict multi-day trend analysis to that date.
- If local CSV date count is below 2, the tab shows a clear insufficient-date message and does not crash.
- If enough dates exist, the tab shows:
  - overview cards
  - 多日偏强 / 由弱转强主题
  - 多日改善主题
  - 多日承压 / 走弱主题
  - 多日趋势明细 dark table
- `verify_runtime.py` reports:
  - whether `daily_theme_snapshots` can be built
  - participating multi-day date count
  - whether multi-day metrics can be built
  - whether trend pool can be built
  - trend summary label and Top 3 trend themes
- Concept fund-flow failure must not affect multi-day trends.
- DEMO still must not write to real CSV.

Forbidden wording check:

- Multi-day trend text must not include action-oriented words such as `买入`, `卖出`, `加仓`, `减仓`, `抄底`, `逃顶`, `推荐买`, `建议买`, `建仓`, or `清仓`.
- Trend explanations must not describe future price or fund NAV prediction.

## v1.2 Theme Taxonomy And Coverage Checks

Theme taxonomy governance is local-config only:

- `config/theme_taxonomy.json` exists and is valid JSON.
- `src/theme_taxonomy.py` can load missing or damaged taxonomy files without crashing.
- `src/theme_coverage.py` can audit a latest industry fund-flow snapshot without network access.
- `theme_pool.py` should prefer taxonomy primary/related sectors and keep fallback rules.
- `theme_concepts.py` should prefer taxonomy concept keywords and keep fallback rules.
- `数据说明` tab should include:
  - 主题库说明
  - 主题定义表
  - 主题覆盖审计
  - 高资金流未覆盖板块表
  - 重复映射 warning 表
  - 主题使用情况表
- `主题雷达` tab should show a compact taxonomy status note.
- If active snapshot is empty, coverage audit should show a clear empty message and not crash.
- If taxonomy JSON is damaged, the app should use fallback taxonomy and remain usable.
- watchlist and fund_profiles theme names should be checked against taxonomy.
- Theme coverage audit must not call AKShare.
- Theme coverage audit must not write CSV.

`verify_runtime.py` should report:

- taxonomy name
- taxonomy theme count
- taxonomy warning count
- watchlist / fund_profiles consistency
- whether theme definition table, sector map, concept keyword table, coverage report, and overlap warning report can be built
- coverage ratio and coverage label
- high-flow uncovered count
- overlap warning count

Forbidden wording check:

- Taxonomy and coverage text must not include action-oriented words such as `买入`, `卖出`, `加仓`, `减仓`, `抄底`, `逃顶`, `推荐买`, `建议买`, `建仓`, or `清仓`.
- Coverage audit must not describe future price or fund NAV prediction.

## v1.3 Observation Brief Checks

The observation brief is a local unified explanation layer:

- Page has an `观察简报` tab.
- The tab explains that it combines theme radar, intraday hotspots, multi-day trends, holding-related pool, and theme coverage audit.
- The brief must reuse existing app results and must not trigger AKShare.
- The brief must not write CSV.
- If active data is empty, the tab shows an EMPTY explanation and does not crash.
- If intraday snapshots are insufficient, the brief says the intraday sample is insufficient.
- If local CSV dates are insufficient, the brief says the multi-day sample is insufficient.
- The brief renders:
  - 摘要
  - 关键观察
  - 口径风险
  - 数据说明
  - 免责声明
- Markdown download should use `st.download_button`.
- Download filename should include the selected date, e.g. `yangjibao_brief_YYYY-MM-DD.md`.
- Forbidden wording validation must run before download.
- If forbidden wording is detected, the app should show a warning and not provide the download button.

`verify_runtime.py` should report:

- whether `insight_brief` can be imported
- whether data context, radar, intraday, multi-day, holding, and coverage summaries can be built
- whether observation brief and markdown can be generated
- brief title
- executive summary preview
- key point count
- forbidden hits

Forbidden wording check:

- Observation brief text must not include action-oriented words such as `买入`, `卖出`, `加仓`, `减仓`, `抄底`, `逃顶`, `推荐买`, `建议买`, `建仓`, or `清仓`.
- Observation brief must not describe future price or fund NAV prediction.

## v1.4 Sample Data Mode Checks

The reproducible demo layer uses bundled synthetic CSV only:

- `sample_data/ticks/sector_flow_2026-01-15.csv` exists.
- `sample_data/ticks/sector_flow_2026-01-16.csv` exists.
- `tools/generate_sample_data.py` can regenerate the sample files deterministically without network access.
- Sample CSV contains `source=SAMPLE` or `data_mode=SAMPLE`.
- `data/ticks/*.csv` remains ignored by git.
- `sample_data/ticks/*.csv` is not ignored by git and should be committed.
- Sidebar has `数据来源模式`.
- Selecting `演示样例数据` displays `SAMPLE`.
- SAMPLE mode must not trigger AKShare.
- SAMPLE mode must not read or write `data/ticks`.
- SAMPLE mode must not be displayed as `LIVE`, `CACHE`, or `HISTORY`.
- SAMPLE mode should allow the main tabs to render:
  - 实时曲线
  - 主题雷达
  - 日内热点
  - 多日趋势
  - 持仓相关池
  - 观察简报
  - 排行榜
  - 数据说明
- SAMPLE mode should support intraday hotspots because at least one sample date has multiple `captured_time` values.
- SAMPLE mode should support multi-day trends because the sample package has at least two dates.
- Observation brief in SAMPLE mode must say the data is synthetic and not real market data.
- If real cache is empty, the app should show a friendly first-run hint: wait for real fetch, use sample data, or use DEMO.
- If sample data is missing or damaged, the app should remain usable and suggest `python tools/generate_sample_data.py`.

`verify_runtime.py` should report:

- sample date count
- latest sample date
- sample captured_time_count
- sample quality_label
- whether sample data can build theme radar, intraday hotspot pool, multi-day trend pool, holding related pool, and observation brief
- sample brief forbidden hits

Forbidden wording check:

- SAMPLE text must not include action-oriented words such as `买入`, `卖出`, `加仓`, `减仓`, `抄底`, `逃顶`, `推荐买`, `建议买`, `建仓`, or `清仓`.
- SAMPLE text must not describe future price or fund NAV prediction.

## v1.5 Deployment And First-run Checks

Deployment preparation should not change analytics logic:

- `requirements.txt` includes at least `streamlit`, `pandas`, `plotly`, `akshare`, `numpy`, and `pytest`.
- `.streamlit/config.toml` exists.
- `.streamlit/config.toml` uses dark theme and `server.headless = true`.
- `.streamlit/secrets.example.toml` exists.
- `.streamlit/secrets.toml` must not be committed.
- `.gitignore` keeps ignoring `.streamlit/secrets.toml`, `.venv/`, `.env`, and `data/ticks/*.csv`.
- `sample_data/ticks/*.csv` must not be ignored.
- README includes:
  - project one-line description
  - project boundary
  - SAMPLE mode explanation
  - Streamlit Cloud deployment notes
  - first-run instructions
- If real cache is empty or real fetch fails without cache, the app shows a clear first-run guide:
  - use SAMPLE data
  - use DEMO for UI testing
  - retry real data later
- SAMPLE mode remains explicit and never appears as `LIVE`, `CACHE`, or `HISTORY`.
- SAMPLE mode must not trigger AKShare.
- SAMPLE mode must not write `data/ticks`.
- Existing tabs must continue to work.

## v1.6 Fund / ETF Theme Exposure CSV Checks

CSV profile configuration must remain a local, non-account template:

- `sample_data/fund_profiles/sample_fund_profiles.csv` exists.
- CSV includes `profile_id`, `profile_name`, `fund_code`, `fund_type`, `description`, `theme_name`, `exposure_weight`, `exposure_role`, and `notes`.
- All sample `fund_code` values use the `DEMO-` prefix.
- CSV does not include real asset fields such as amount, shares, cost, profit, account, or balance.
- CSV themes should match `config/theme_taxonomy.json`.
- Unknown themes are reported by validation.
- Negative or nonnumeric weights are reported as errors.
- Weights above 1 and duplicated profile-theme rows are reported as warnings.
- Holding-related tab shows CSV validation overview, profile summary, theme exposure detail, and observation summary.
- CSV import does not trigger AKShare.
- CSV import does not write `data/ticks`.
- CSV import does not overwrite `config/fund_profiles.json`.
- CSV text and generated observation text must not include action-oriented words such as `买入`, `卖出`, `加仓`, `减仓`, `抄底`, `逃顶`, `推荐买`, `建议买`, `建仓`, or `清仓`.
- CSV text must not describe future price or fund NAV prediction.

`smoke_check.py` should report:

- sample fund profile row count
- sample profile count
- validation label
- warning count
- error count

`verify_runtime.py` should report:

- fund profile csv path
- csv profile count
- csv row count
- csv validation label
- csv warning count
- csv error count
- whether profile summary, theme exposure table, theme radar merge, and observation summary can be built
- profile observation forbidden hits

`smoke_check.py` should report:

- `.streamlit/config.toml`
- `.streamlit/secrets.example.toml`
- sample CSV files
- numpy import
- sample catalog date count

`verify_runtime.py` should report:

- requirements check
- theme.base
- server.headless
- browser.gatherUsageStats
- whether real `secrets.toml` exists in the project directory

Forbidden wording check:

- Deployment and first-run text must not include action-oriented investment wording.

## Data-source roadmap

This Streamlit MVP intentionally keeps the request strategy small:

- Current version only switches between `行业资金流` and `概念资金流`.
- It does not add high-frequency full crawling across industry, concept, region, today, 5-day, and 10-day dimensions.
- Next direction: backend full capture, frontend curated display.
- Recommended order: stabilize industry fund flow first, then gradually add concept fund flow, regional fund flow, 5-day, and 10-day views.

The reason is simple: the concept fund-flow endpoint can occasionally fail with proxy or upstream errors. Increasing request volume before the status and cache path are stable would make the dashboard less trustworthy.

## v3.8 Evidence-Backed Theme Observation Checks

- `src/theme_observation_evidence.py` exists and can be imported.
- `tools/inspect_theme_evidence.py` exists and supports SAMPLE / REAL read-only inspection.
- `src/theme_taxonomy.py` exposes deterministic taxonomy and theme-definition fingerprints.
- `src/theme_pool.py` can build a theme snapshot with trace while reusing the canonical matching and aggregation path.
- Strict representative, representative and breadth modes expose actual included members and excluded members.
- Theme state evidence includes aggregation inputs, aggregate value, threshold mapping and derived state.
- Historical evidence readiness includes separate history span, intraday depth and coverage consistency states.
- SAMPLE theme evidence is explicitly labeled as synthetic demo evidence.
- REAL and SAMPLE evidence are not silently combined.
- Streamlit Theme Radar and Multi-Day tabs expose compact factual evidence panels without changing the main calculation.
- Observation brief exports include compact provenance metadata without dumping full trace data.
- Theme evidence CLI does not call AKShare, write CSV, write logs, mutate taxonomy or read personal holdings.
- Documentation explains analytical provenance versus investment rationale.
- Tests remain offline and deterministic.
- Page and docs avoid trading, prediction, recommendation or investment-action wording.

## v3.9 Theme Taxonomy Calibration Checks

- `APP_VERSION` is `v3.9`.
- `CHANGELOG.md` contains a `v3.9` entry.
- `src/theme_taxonomy_audit.py` exists and can be imported.
- `tools/audit_theme_taxonomy.py` exists and supports SAMPLE / REAL read-only audit.
- Legacy `primary_sectors` and `related_sectors` remain compatible with the theme taxonomy loader.
- Theme member definitions expose role, strict representative flag, canonical name, mapping source, mapping method, rationale and aliases.
- Reused canonical members are reported as warnings or ambiguities, not silently assigned to one theme.
- Alias collisions are reported as structural errors.
- Cross-theme overlap audit reports shared members, overlap ratio and overlap state.
- Source-universe coverage audit reports denominator semantics, mapped rows, ambiguous rows and unmapped rows.
- SAMPLE coverage uses only `sample_data/ticks` and remains labeled as synthetic demo evidence.
- REAL coverage uses local `data/ticks` only when available and does not affect public demo readiness.
- Theme evidence contribution tables include canonical member, matched-by mode, alias usage, ambiguity status and mapping provenance.
- Streamlit Data Explanation exposes a compact taxonomy audit panel without adding a new tab or changing theme calculations.
- `tools/audit_theme_taxonomy.py` does not call AKShare, write CSV, write SQLite, mutate taxonomy or combine SAMPLE and REAL evidence.
- `smoke_check.py`, `verify_runtime.py`, `cloud_preflight.py` and `release_check.py` include the taxonomy audit assets.
- Tests remain offline and deterministic.
- Page and docs avoid trading, prediction, recommendation or investment-action wording.

## v3.10 Theme Dynamics Checks

- `APP_VERSION` is `v3.10`.
- `CHANGELOG.md` contains a `v3.10` entry.
- `src/theme_dynamics.py` exists and can be imported.
- `tools/inspect_theme_dynamics.py` exists and supports SAMPLE / REAL read-only inspection.
- Theme observation fact grain includes `theme_name`, `trade_date`, `captured_time_bucket`, `calculation_mode`, `source_mode`, `taxonomy_fingerprint` and `theme_definition_fingerprint`.
- Theme dynamics reuses canonical theme-pool trace output instead of duplicating the matching or state formula.
- Duplicate observation grains are surfaced as warnings and not silently overwritten.
- State transition trace reports observed state path, transition counts, historical occupancy shares and longest observed streaks using cached observations as the denominator.
- Cross-date evolution uses latest snapshot per trade date and does not treat every intraday point as a separate day.
- Scope divergence compares strict representative, representative and breadth modes only when source mode and fingerprints align.
- Member structural divergence uses already-included member traces and does not rematch source rows.
- SAMPLE dynamics is explicitly labeled as synthetic demo evidence.
- REAL dynamics uses local `data/ticks` only when available and remains local cache evidence.
- Streamlit Multi-Day and Observation Brief sections expose compact factual dynamics evidence without replacing existing calculations.
- `tools/inspect_theme_dynamics.py` does not call AKShare, write CSV, write SQLite, mutate taxonomy or combine SAMPLE and REAL evidence.
- `smoke_check.py`, `verify_runtime.py`, `cloud_preflight.py` and `release_check.py` include the theme dynamics assets.
- Tests remain offline and deterministic.
- Page and docs avoid trading, prediction, recommendation or investment-action wording.

## v3.11 Analytical Grain Integrity Checks

- `APP_VERSION` is `v3.11`.
- `CHANGELOG.md` contains a `v3.11` entry.
- Raw event observation grain is explicit: `snapshot_event_id`, `theme_name`, `calculation_mode`, `source_mode`, `theme_definition_fingerprint`.
- Bucketed analytical observation grain is explicit: `theme_name`, `trade_date`, `captured_time_bucket`, `calculation_mode`, `source_mode`, `taxonomy_fingerprint`, `theme_definition_fingerprint`.
- `build_theme_observation_events()` preserves physical snapshot lineage and exact captured timestamps.
- Bucket collisions are reported separately from true raw event duplicates.
- Canonical bucket observations use the centralized `latest_valid_snapshot_in_bucket` policy.
- Non-selected events remain preserved in contributing lineage.
- State transition traces, occupancy shares and streaks default to canonical bucket observations.
- Scope divergence exposes `alignment_status`, compared snapshot IDs and selected event IDs.
- `tools/inspect_observation_grain.py` exists and supports SAMPLE / REAL read-only inspection.
- The grain CLI reports raw events, bucket collision summary and canonical observation examples without printing raw market rows.
- Streamlit Multi-Day evidence panel shows dynamics basis, materialization policy and bucket collision counts.
- `smoke_check.py`, `verify_runtime.py`, `cloud_preflight.py` and `release_check.py` include analytical grain assets.
- No `drop_duplicates()` shortcut is presented as the analytical solution.
- Tests remain offline and deterministic.
- Page and docs avoid trading, prediction, recommendation or investment-action wording.

## v3.12 Structural Regime Signature Checks

- `APP_VERSION` is `v3.12`.
- `CHANGELOG.md` contains a `v3.12` entry.
- `src/theme_regimes.py` exists and can be imported.
- `tools/inspect_theme_regimes.py` exists and supports SAMPLE / REAL read-only inspection.
- Structural regime signatures are composed from deterministic governed dimensions: headline state, scope divergence state and member structural state.
- Signature IDs are deterministic, but the human-readable signature remains visible.
- Signatures default to v3.11 canonical bucket observations and do not use raw physical events as the default basis.
- Scope divergence is reused from `build_scope_divergence_table()`; member structure is reused from the existing theme trace output.
- Episodes are contiguous observed canonical-observation sequences with the same structural signature.
- Timestamp spans are labeled as observed timestamp spans, not continuous regime duration.
- Transition traces report observed transition counts, not future-oriented measures.
- Headline-preserving structural transitions are identified when the headline state remains unchanged while scope/member structure changes.
- State-equivalent analysis groups canonical observations by headline state and reports observed structural shares with an explicit denominator.
- REAL and SAMPLE, different theme definitions and incompatible taxonomy fingerprints are not silently combined.
- Streamlit Multi-Day / Theme Dynamics Evidence includes a compact Structural Regime Evidence panel without replacing existing multi-day logic.
- Observation Brief integration remains concise and descriptive.
- The regime layer does not introduce clustering, embeddings, opaque scores, strategy returns, trading signals or investment-action wording.
- Tests remain offline and deterministic.

## v3.13 Cross-Theme Relationship Evidence Checks

- `APP_VERSION` is `v3.13`.
- `CHANGELOG.md` contains a `v3.13` entry.
- `src/theme_relationships.py` exists and can be imported.
- `tools/inspect_theme_relationships.py` exists and supports SAMPLE / REAL read-only inspection.
- Theme pairs are deterministic and unordered.
- Pair alignment uses exact canonical bucket observations only.
- Missing pair observations remain visible as alignment gaps.
- Semantic overlap reuses the taxonomy overlap audit.
- Headline agreement, same-sign share, structural-regime alignment and co-transition counts expose denominators.
- No relationship score, correlation ranking, mechanism claim, prediction or investment-action wording is introduced.
- Tests remain offline and deterministic.

## v3.14 Analytical Robustness Checks

- `APP_VERSION` is `v3.14`.
- `CHANGELOG.md` contains a `v3.14` entry.
- `src/analytical_robustness.py` exists and can be imported.
- `tools/audit_analytical_robustness.py` exists and supports SAMPLE / REAL read-only audit.
- Analytical specification identity includes bucket width, materialization policy, calculation mode, source mode, taxonomy fingerprint, canonical basis and threshold fingerprint.
- Changing bucket width, materialization policy or calculation mode changes the specification ID.
- The production default canonical policy remains `latest_valid_snapshot_in_bucket`.
- Bucket-width sensitivity uses pre-declared `1,5,10` minute variants.
- Materialization-policy sensitivity is an audit variant and does not switch production behavior.
- Calculation scopes are compared as semantic scopes and are not ranked.
- Evidence sufficiency exposes observation count, represented trade dates, observations by date, max-date observation share, bucket count and alignment gaps.
- Threshold-boundary proximity uses existing state thresholds and does not mutate them.
- Relationship robustness exposes aligned-observation ranges, same-sign ranges, exact-state ranges, same-regime ranges, structural-contrast ranges and per-date results.
- Relationship topology rows include numerator/denominator context and represented trade dates.
- Low-evidence pairs remain inspectable but are gated from ranked display rows by explicit display sufficiency thresholds.
- Streamlit Multi-Day evidence includes a compact Analytical Robustness Evidence panel without replacing existing multi-day logic.
- Observation Brief integration remains concise and uses factual specification range wording only.
- The robustness layer does not introduce robustness scores, confidence scores, p-values, prediction, trading signals or investment-action wording.
- Tests remain offline and deterministic.

## v3.15 Provider Semantics and Continuity Checks

- `APP_VERSION` is `v3.15`.
- `CHANGELOG.md` contains a `v3.15` entry.
- `src/provider_contracts.py`, `src/provider_comparability.py`, `src/provider_registry.py` and `src/provider_network_diagnostics.py` exist and can be imported.
- `tools/audit_provider_semantics.py` exists and supports offline registry, primary, candidate, compare and eligibility inspection.
- `tools/diagnose_provider_network.py` exists and reports proxy/DNS/request/provider-stage diagnostics without printing proxy values or credentials.
- The primary provider contract is explicit for `ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")`.
- Semantic contract IDs are deterministic, formatting-insensitive and change when meaningful semantic fields change.
- Candidate provider contracts are classified by semantic dimensions rather than similar API names or similar column names.
- Comparability states include `equivalent`, `conditionally_comparable`, `non_equivalent` and `unknown`.
- Continuity eligibility is separate from runtime provider policy.
- Default runtime provider policy remains `primary_only`.
- No silent automatic fallback is enabled.
- New normalized REAL snapshots can preserve provider ID, provider contract ID, semantic contract fingerprint and upstream origin.
- Historical evidence reports provider contract counts, provider segment counts, provider segments and source-homogeneous state.
- Multi-provider history is not silently presented as source-homogeneous.
- Streamlit Data Explanation includes a compact Provider Semantics & Continuity panel without running live probes on render.
- `smoke_check.py`, `verify_runtime.py`, `cloud_preflight.py` and `release_check.py` recognize provider semantics readiness.
- Deterministic tests remain offline and do not require live AKShare.

## v3.16 Provider-Contract-Aware Analytical Continuity Checks

- `APP_VERSION` is `v3.16`.
- `CHANGELOG.md` contains a `v3.16` entry.
- `src/analytical_continuity.py` exists and can be imported.
- `tools/audit_analytical_continuity.py` exists and supports SAMPLE / REAL read-only audits.
- SAMPLE observations resolve to a dedicated synthetic demo provider contract segment.
- REAL observations with explicit provider contract ID and fingerprint resolve separately from explicit-ID-only, inferred and unknown lineage.
- Inferred legacy provider metadata is not silently upgraded to explicit verified continuity.
- Bucketed analytical observation grain includes `analytical_continuity_segment_id`.
- Canonical materialization does not let observations from different continuity segments compete in one bucket.
- Scope divergence comparisons preserve continuity segment boundaries.
- Structural regime episodes split across continuity segment boundaries even when structural signatures match.
- Cross-theme pair alignment requires the same continuity segment.
- Analytical robustness reports continuity-universe metadata and does not hide provider-contract changes as bucket or mode sensitivity.
- `smoke_check.py`, `verify_runtime.py` and `quality_gate.py` recognize analytical continuity readiness.
- Tests remain offline and deterministic, and do not call live AKShare or write `data/ticks` / `data/warehouse`.
