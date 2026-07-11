# Release Checklist

Use this checklist before publishing the repository, updating a portfolio link, or deploying to Streamlit Cloud.

## 1. Automated Checks

```bash
python tools/quality_gate.py
python tools/cloud_preflight.py
python tools/release_check.py
python tools/smoke_check.py
python tools/verify_runtime.py
python tools/inspect_history_evidence.py --source-mode REAL
python tools/inspect_history_evidence.py --data-dir sample_data/ticks --source-mode SAMPLE --matrix
python tools/audit_provider_semantics.py --registry
python tools/audit_provider_semantics.py --primary
python tools/audit_provider_semantics.py --eligibility
python tools/audit_analytical_continuity.py --source SAMPLE
python tools/audit_analytical_continuity.py --source REAL
python tools/audit_analytical_eligibility.py --source SAMPLE
python tools/audit_analytical_eligibility.py --source REAL
python tools/audit_evidence_accumulation.py --source SAMPLE
python tools/audit_evidence_accumulation.py --source REAL
python -m pytest -q
python -m compileall app.py src tests tools
```

- `release_check.py` should report no errors.
- `quality_gate.py` should pass before a release-oriented push.
- `release_check.py` should confirm APP_VERSION has a matching CHANGELOG entry.
- `release_check.py` should report no tracked forbidden files.
- `release_check.py` should report SAMPLE data contract status.
- `smoke_check.py` / `verify_runtime.py` should report real cache evidence and collector audit-log visibility without requiring real cache in CI.
- `smoke_check.py` / `verify_runtime.py` should report collection policy, ingestion metrics, real cache coverage labels and bounded runner readiness without calling live AKShare.
- `smoke_check.py` / `verify_runtime.py` should report historical evidence readiness, SAMPLE replay provenance and captured_time coverage matrix shape without calling live AKShare.
- `inspect_history_evidence.py` should inspect REAL cache gracefully even when no local real cache exists, and should inspect SAMPLE history with a readable matrix.
- `audit_provider_semantics.py` should report an explicit primary provider contract, candidate comparability counts, `primary_only` runtime policy, and no silent fallback.
- `audit_analytical_continuity.py` should report continuity segments, canonical observation counts, cross-segment collision count and no network use.
- `audit_analytical_eligibility.py` should report historical availability separately from qualified readiness; unresolved REAL legacy history should remain auditable but excluded from qualified analytical workloads.
- `audit_evidence_accumulation.py` should report physical captures, qualified captures, predeclared acquisition-cell coverage, missing cells and marginal contribution counts without network use or writes.
- `cloud_preflight.py` should confirm `docs/ARCHITECTURE.md`, `docs/DATA_FLOW.md` and `docs/OPERATIONS.md` exist.
- `release_check.py` and `cloud_preflight.py` should confirm `docs/REAL_DATA_INGESTION.md`, `tools/collect_real_snapshot.py`, `tools/run_collection_session.py`, `src/collection_policy.py` and `src/ingestion_metrics.py` exist.
- Optional static report: `python tools/release_check.py --write-report docs/release_readiness_report.md`.
- Warnings should be reviewed manually before release.
- Tests and compile checks must pass.

## 1.1 Public Demo Runtime Checks

```bash
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 streamlit run app.py
```

- Public demo profile should default to `SAMPLE 演示样例数据`.
- Public demo profile should default to `作品集演示模式`.
- Without `FUND_FLOW_PUBLIC_DEMO`, a public/cloud first visit with no `data/ticks` but available `sample_data/ticks` should still default to SAMPLE.
- SAMPLE / 合成演示数据说明 should be visible on first visit.
- No warehouse: the app should still run and show manual rebuild guidance.
- Opening the page should not write `data/ticks`.
- Opening the page should not create or write `data/warehouse/fund_flow.sqlite`.
- Users should still be able to manually switch data source and presentation mode.
- Page copy should not contain trading actions, fund recommendations, or future prediction wording.

## 2. Data Safety Checks

```bash
git status --short
git check-ignore -v data/ticks/*.csv
git check-ignore -v data/logs/collector_runs.jsonl
git check-ignore -v logs/collector_runs.jsonl
git check-ignore -v data/warehouse/fund_flow.sqlite
git check-ignore -v "*.sqlite"
git check-ignore -v "*.db"
git check-ignore -v .env
git check-ignore -v .venv/
git check-ignore -v .streamlit/secrets.toml
```

- Do not commit real `data/ticks/*.csv` snapshots.
- Do not commit local collector logs under `data/logs/` or `logs/`.
- Do not commit `data/warehouse/*.sqlite`, `*.sqlite3`, or `*.db`.
- Do not commit `.env`, `.streamlit/secrets.toml`, `.venv/`, `__pycache__/`, or `.pytest_cache/`.
- `sample_data/ticks/*.csv` and demo brief files are public portfolio assets and should remain trackable.

## 2.1 Local Real Data Collection Checks

```bash
python tools/collect_real_snapshot.py --dry-run
python tools/collect_real_snapshot.py --no-network
python tools/collect_real_snapshot.py --dry-run --no-log
python tools/probe_akshare.py
python tools/probe_akshare.py --json
python tools/run_collection_session.py --max-runs 3 --interval-seconds 0 --dry-run --no-log --ignore-session
```

- These checks may depend on live AKShare/network availability and should be interpreted separately from unit tests.
- Probe output should include AKShare version, `stock_sector_fund_flow_rank`, response type, row count, schema fingerprint, normalization status and contract status when available.
- Provider failures should be classified as `network_error`, `timeout_error`, `provider_parse_error`, `empty_response`, `schema_drift`, `normalization_error` or `contract_error` rather than hidden behind generic wording.
- `--dry-run` should not write `data/ticks`.
- `--no-network` should not access AKShare and should not write `data/ticks`.
- `--no-log` should suppress `data/logs/collector_runs.jsonl` for that run.
- `run_collection_session.py` must use a bounded `--max-runs` and must not create a scheduler, daemon, Streamlit loop, CSV warehouse, or background service.
- `run_collection_session.py --dry-run --no-log --ignore-session` should return a readable session summary and should not write `data/ticks` or `data/logs`.
- Ingestion metrics should label success rate as `success / write-intent runs`, excluding `dry_run` and `no_network`.
- A successful collector run without `--dry-run` may create ignored real CSV files under `data/ticks`; never stage those files.
- Normal collector runs may create ignored audit logs under `data/logs/collector_runs.jsonl`; never stage those logs.
- After local collection, the `数据说明` tab should show real cache coverage, latest cache date/time, staleness status, empty/malformed file counts, and latest collector run status.
- After local collection, `tools/inspect_history_evidence.py --source-mode REAL` should show snapshot-level lineage, schema fingerprint consistency and selected-date replay provenance without printing row-level private data.
- `tools/inspect_theme_evidence.py --theme "半导体/芯片链" --source-mode SAMPLE --trace` should show taxonomy fingerprint, matched members, aggregation method and threshold mapping.
- Theme Radar evidence panels should label SAMPLE evidence as synthetic demo evidence and should not frame evidence as investment rationale.
- `python tools/audit_theme_taxonomy.py --source-mode SAMPLE --coverage --overlap --top-overlaps 10` should run as a read-only taxonomy calibration audit.
- `python tools/inspect_theme_dynamics.py --theme "半导体/芯片链" --source-mode SAMPLE --state-trace --scope-divergence --member-divergence` should show observed state path, cross-scope divergence and member structural divergence without writing CSV/SQLite.
- `python tools/inspect_observation_grain.py --source-mode SAMPLE --json` should show raw event grain, bucketed analytical grain, bucket collision summary and canonical materialization policy.
- `python tools/inspect_observation_grain.py --source-mode REAL --collisions --canonical` may be run locally when real cache exists; missing real cache should remain a safe, readable state.
- `python tools/inspect_theme_regimes.py --theme "半导体/芯片链" --source-mode SAMPLE --episodes --transitions --state-equivalent` should show structural signatures, observed episodes and headline-preserving structural transitions without writing CSV/SQLite.
- `python tools/audit_analytical_robustness.py --source-mode SAMPLE --theme "半导体/芯片链" --bucket-minutes "1,5,10" --evidence-sufficiency --threshold-boundaries --json` should show analytical specification IDs, evidence sufficiency and threshold-boundary evidence without writing CSV/SQLite.
- `python tools/audit_analytical_robustness.py --source-mode SAMPLE --pair "AI算力/TMT::半导体/芯片链" --mode "strict_representative" --bucket-minutes "1,5,10" --date-concentration --json` should show aligned-observation ranges, represented trade dates, per-date results and denominator context.
- `python tools/audit_analytical_continuity.py --source SAMPLE --theme "半导体/芯片链" --pair "AI算力/TMT::半导体/芯片链" --json` should show SAMPLE synthetic continuity segments and should not call AKShare or write CSV/SQLite.
- `python tools/audit_analytical_continuity.py --source REAL --json` should remain readable when no local real cache exists.
- `python tools/audit_evidence_accumulation.py --source SAMPLE --json` should show SAMPLE physical capture events, qualified demo captures and acquisition-cell coverage without treating SAMPLE as real history.
- `python tools/audit_evidence_accumulation.py --source REAL --json` should show REAL physical captures and exclude unresolved legacy captures from qualified acquisition coverage until explicit verified provider contract lineage exists.
- `python tools/materialize_market_session_calendar.py --validate-only --json` should validate `config/market_session_calendar.json` without provider access or writes.
- `python tools/run_collection_session.py --no-network --no-log --max-runs 1 --json` should report market-session policy identity, source classification, market scope and current date eligibility without writing CSV or logs.
- A collector success should be reconciled with evidence accumulation: it is not sufficient by itself unless the capture is qualified and contributes to a predeclared acquisition cell.
- `python tools/inspect_theme_relationships.py --source-mode SAMPLE --mode "strict_representative" --top-state-alignment --limit 10` should show display sufficiency thresholds, represented trade dates and numerator/denominator context.
- Bucket collisions should be described as multiple valid captured events sharing one analytical bucket, not as generic duplicate removal.
- Taxonomy audit warnings such as reused members or ambiguous source names should be reviewed as mapping-governance notes, not app failures.
- Missing real cache or missing collector logs on Streamlit Cloud is expected and should not be treated as a public demo failure.
- Any AKShare failure should be documented as a live data source/network limitation, not replaced with fake real data.
- `python tools/diagnose_provider_network.py` may be run for proxy/DNS/request/provider-stage diagnosis. It should print only proxy presence flags and sanitized failures, not proxy values or credentials.
- Candidate provider/API availability must not be treated as semantic equivalence. Different row grain, universe semantics, time semantics or value semantics should block silent continuity.

## 3. Demo Checks

```bash
python tools/export_sample_brief.py
python tools/rebuild_local_warehouse.py --include-sample --clear
streamlit run app.py
```

- SAMPLE demo brief should contain `主题历史观察摘要`.
- SAMPLE demo brief should clearly say SAMPLE / synthetic demo data / not real market data.
- The SAMPLE warehouse should be rebuildable from `sample_data/ticks`.
- The app should work without real local `data/ticks` cache.

## 4. Manual UI Checks

- First screen clearly explains what the app is, which data mode is active, and how to read the main tabs.
- SAMPLE status is visible and not presented as real market data.
- Theme radar displays normally.
- Theme history chart displays normally after SAMPLE warehouse rebuild.
- Cross-theme relationship evidence displays aligned observation counts, semantic overlap, same-sign observed share and structural contrast without showing a relationship score.
- Analytical Robustness Evidence displays specification identity, evidence depth, observed result ranges and date concentration without showing confidence or significance language.
- Warehouse Explorer displays SAMPLE data and read-only consistency information.
- Observation brief can be generated and downloaded.
- No local path, secret, account data, or real private cache content is visible.
- Page copy only describes historical observed states and does not imply future prediction.

## 5. Final GitHub Checks

- GitHub repo description is filled:
  `A Streamlit dashboard for A-share sector/theme fund-flow observation, with reproducible sample-data demo mode.`
- GitHub topics are set: `streamlit`, `plotly`, `pandas`, `akshare`, `finance-dashboard`, `data-visualization`, `portfolio-project`.
- GitHub About website URL is filled only after the real Streamlit Cloud URL is available.
- Public repo settings checklist exists: `docs/PUBLIC_REPO_SETTINGS.md`.
- Public release audit exists: `docs/PUBLIC_RELEASE_AUDIT.md`.
- Portfolio support docs exist: `docs/PORTFOLIO_PRESENTATION.md`, `docs/INTERVIEW_TALKING_POINTS.md`, and `docs/RESUME_SNIPPETS.md`.
- Engineering docs exist: `docs/ARCHITECTURE.md` and `docs/DATA_FLOW.md`.
- Operations docs exist: `docs/OPERATIONS.md`.
- `LICENSE` exists and matches the intended public sharing policy.
- README links point to existing files.
- README does not include missing screenshot references.
- `docs/demo_briefs/sample_observation_brief.md` is readable in GitHub Markdown preview.
- `docs/screenshots/SCREENSHOT_GUIDE.md` is actionable.
- `docs/RELEASE_CHECKLIST.md` matches the current release workflow.
- `git status --short` does not show real CSV snapshots, SQLite databases, secrets, virtualenv files, or cache folders.

## 6. Boundary Checks

- The project is a Streamlit + CSV MVP, not a production trading system.
- CSV remains the source of truth; SQLite is a rebuildable local query index.
- SAMPLE and DEMO do not represent real market quotes.
- The project does not connect to broker accounts or read personal holdings.
- The project does not provide trading actions, fund recommendations, or future predictions.
- Cross-theme relationship evidence remains descriptive and does not collapse semantic overlap and observed dynamic alignment into one score.
- Analytical robustness evidence remains descriptive and does not collapse specification sensitivity into one score.
