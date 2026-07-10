# CHANGELOG

## v3.18

- Qualified Evidence Accumulation Protocol, Temporal Sampling Frame and Coverage Gap Audit.
- Added `src/evidence_accumulation.py` to separate physical capture events from sector rows, theme rows and analytical bucket materialization.
- Added deterministic acquisition frames based on configured collection sessions, with explicit cell IDs, boundary convention and covered / missing acquisition-cell counts.
- Added marginal evidence contribution states so clustered captures in the same cell are tracked as additional captures instead of being counted as new temporal coverage.
- Hardened market-session date eligibility so REAL captures cannot enter qualified acquisition coverage solely because they were fetched inside a configured clock session.
- Added a conservative offline market-session date policy: dates without declared coverage remain `market_calendar_unverified`, while SAMPLE remains synthetic demo evidence.
- Added `tools/audit_evidence_accumulation.py` for offline SAMPLE / REAL acquisition coverage audits without AKShare calls, CSV writes or SQLite writes.
- Streamlit Data Explanation now shows compact REAL and SAMPLE evidence accumulation cards beside historical availability and analytical eligibility.
- Smoke, runtime and quality-gate checks now verify evidence accumulation assets and SAMPLE acquisition coverage without requiring live network access.
- This layer does not change provider fetches, theme formulas or warehouse schema; it clarifies when existing captures enter a qualified acquisition universe.

## v3.17

- Contract-Qualified Historical Evidence and Analytical Eligibility.
- Added `src/analytical_eligibility.py` to separate historical CSV availability from workload-qualified analytical readiness.
- REAL observations now require explicit verified primary-provider contract identity before they can enter qualified continuity, regime, relationship or robustness analytics.
- SAMPLE synthetic observations remain eligible for SAMPLE demo analytics only, with source mode preserved.
- Regime, relationship and robustness evidence now filter denominator universes through the analytical eligibility gate while preserving readable historical evidence for audit.
- Added `tools/audit_analytical_eligibility.py` for read-only SAMPLE / REAL audits without AKShare calls, CSV writes or SQLite writes.
- Streamlit Data Explanation now shows historical availability beside contract-qualified analytical readiness so legacy unresolved history cannot inflate qualified readiness.
- This layer does not change collection, theme formulas, provider contracts or public demo behavior; it only clarifies which observations are eligible for analytical workloads.

## v3.16

- Provider-contract-aware Analytical Continuity.
- Added `src/analytical_continuity.py` to resolve provider contract lineage with explicit provenance states: explicit verified, explicit id only, inferred from provider metadata, SAMPLE synthetic and unknown.
- Bucketed canonical observation grain now includes `analytical_continuity_segment_id`, so observations from different provider-contract continuity segments do not compete for the same canonical bucket.
- Scope divergence, structural regime episodes and cross-theme relationship alignment now preserve analytical continuity segment boundaries.
- Analytical robustness reports continuity-universe metadata alongside specification sensitivity so provider-contract changes are not hidden as bucket-width or calculation-mode effects.
- Added `tools/audit_analytical_continuity.py` for read-only SAMPLE / REAL continuity audits without live AKShare access, CSV writes or SQLite writes.
- Smoke, runtime and quality-gate checks now recognize analytical continuity readiness.
- This layer preserves physical snapshot identity while preventing analytically incompatible provider-contract history from being silently treated as one continuous evidence line.

## v3.15

- Provider Semantics Registry, Source Comparability and Continuity Gate.
- Added explicit provider semantic contracts for the current AKShare / Eastmoney primary path: `ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")`.
- Added deterministic semantic contract fingerprints, provider registry inspection and source comparability classification across equivalent / conditionally comparable / non-equivalent / unknown states.
- Added a continuity eligibility gate that separates semantic eligibility from runtime fallback policy. The default runtime policy remains `primary_only`; no silent fallback is enabled.
- New normalized REAL snapshots can preserve provider contract identity, and historical evidence can report provider contract counts, provider segments and source-homogeneous state.
- Added read-only provider semantic audit and network diagnostic CLIs: `tools/audit_provider_semantics.py` and `tools/diagnose_provider_network.py`.
- Streamlit Data Explanation now includes a compact Provider Semantics & Continuity evidence panel without running live network diagnostics on render.
- Release, smoke, runtime and cloud checks now recognize provider semantics assets and keep CI offline/deterministic.
- This layer is source-governance evidence only: available APIs are not treated as comparable facts, and provider availability does not create trading signals, prediction or investment recommendation.

## v3.14

- Analytical Robustness, Specification Sensitivity and Evidence Sufficiency.
- Added `src/analytical_robustness.py` to define deterministic analytical specification identity across bucket width, materialization policy, calculation scope, source mode, taxonomy fingerprint and threshold fingerprint.
- Added evidence sufficiency profiles with observation counts, represented trade dates, observations by date, max-date observation share, bucket count and alignment gap context.
- Added pre-declared bucket-width sensitivity for 1 / 5 / 10 minute buckets and materialization-policy audit variants while keeping the production default `latest_valid_snapshot_in_bucket` unchanged.
- Added threshold-boundary proximity evidence based on existing theme state thresholds without changing or perturbing them.
- Added `tools/audit_analytical_robustness.py` for read-only SAMPLE / REAL robustness audits without AKShare calls or cache writes.
- Cross-theme topology rows now expose numerator/denominator context, represented trade dates and display sufficiency guardrails.
- Streamlit Multi-Day evidence now includes a compact Analytical Robustness Evidence panel; Observation Briefs can include concise specification range qualifiers.
- This layer reports factual ranges and observed variation only: no robustness score, no confidence score, no p-value theatre, no prediction and no investment recommendation.

## v3.13

- Cross-Theme Alignment Topology and Semantic-Dynamic Contrast.
- Added `src/theme_relationships.py` to build deterministic unordered theme-pair evidence from aligned canonical bucket observations.
- Added `tools/inspect_theme_relationships.py` for read-only SAMPLE / REAL pair inspection and factual topology tables without calling AKShare or writing cache files.
- Pair evidence distinguishes semantic taxonomy overlap, exact headline-state agreement, same-sign observed share, structural-regime alignment and observed co-transition counts.
- Reuses v3.9 taxonomy overlap audit and v3.12 structural regime signatures instead of creating a second overlap formula or a black-box relationship score.
- Streamlit Multi-Day evidence now includes a compact Cross-Theme Relationship Evidence panel and optional topology table.
- Observation Brief exports can include concise relationship evidence with explicit denominator wording.
- The layer remains descriptive: no mechanism claim, no temporal-order model, no correlation-based trading signal, no future-oriented relationship forecast and no investment recommendation.

## v3.12

- Structural Regime Signatures and State-Equivalent Divergence.
- Added `src/theme_regimes.py` to compose deterministic human-readable structural signatures from governed headline state, scope divergence state and member structural state.
- Added regime episodes, observed transition traces, headline-preserving structural transitions and state-equivalent structural analysis on top of canonical bucket observations.
- Added `tools/inspect_theme_regimes.py` for read-only SAMPLE / REAL structural regime inspection without calling AKShare or writing cache files.
- Streamlit Theme Dynamics Evidence now includes a compact Structural Regime Evidence section with signature legend, episode table and observed-share tables.
- Observation Brief exports can include concise structural-regime evidence while preserving no-prediction and no-advice wording.
- Smoke/runtime/cloud/release checks now recognize structural regime assets and SAMPLE regime evidence.
- The layer remains descriptive and deterministic: no clustering, no black-box score, no transition forecast, no trading signal and no investment recommendation.

## v3.11

- Analytical Grain Integrity and Canonical Observation Materialization.
- Split theme dynamics into explicit raw event observation grain and bucketed analytical observation grain.
- Added bucket collision analysis so multiple valid captured events in one time bucket are not mislabeled as ordinary duplicates.
- Materialized canonical bucket observations with the centralized `latest_valid_snapshot_in_bucket` policy while preserving contributing event lineage.
- Added `tools/inspect_observation_grain.py` for read-only SAMPLE / REAL grain audits, collision summaries and canonical materialization evidence.
- Theme dynamics state paths, occupancy shares, streaks and scope divergence now default to canonical bucket observations with explicit denominator wording.
- Streamlit evidence panels, smoke/runtime/cloud/release checks and docs now surface dynamics basis, materialization policy and bucket-collision evidence without changing theme calculation formulas.
- The layer remains descriptive and offline-safe: no AKShare fetch, no CSV/SQLite writes, no prediction and no investment recommendation.

## v3.10

- Theme Dynamics Cube, state transition trace and structural divergence.
- Added `src/theme_dynamics.py` and `tools/inspect_theme_dynamics.py` for deterministic, read-only inspection of theme observation facts across trade date, captured time bucket, calculation mode, source mode and taxonomy fingerprints.
- Theme dynamics reuses the canonical `theme_pool` trace path and records state paths, historical occupancy shares, latest-per-date evolution, cross-scope divergence and member-level structural divergence without changing the displayed theme calculation formula.
- Streamlit Multi-Day and Observation Brief surfaces can show compact theme dynamics evidence for SAMPLE or local REAL cache when available.
- Smoke/runtime/cloud/release checks now verify theme dynamics assets and SAMPLE read-only evidence without requiring live AKShare or writing CSV/SQLite.
- The dynamics layer describes observed historical cache states only; it is not a forecast, backtest, trading rationale or investment recommendation.

## v3.9

- Theme taxonomy calibration and overlap audit.
- Added `src/theme_taxonomy_audit.py` and `tools/audit_theme_taxonomy.py` for deterministic, read-only inspection of theme member roles, mapping provenance, cross-theme overlap and source-universe coverage.
- Theme taxonomy normalization now exposes member roles, strict representative flags, mapping source/method/rationale and explicit alias resolution while keeping the legacy `primary_sectors` / `related_sectors` schema compatible.
- Theme evidence traces now include canonical member names, exact/contains match type, alias usage, ambiguity status and mapping provenance without changing the existing theme calculation formula.
- Streamlit Data Explanation now includes a compact taxonomy audit panel for validation warnings, overlap pairs, calibration summary and SAMPLE/REAL coverage denominator notes.
- Smoke/runtime/cloud/release checks now verify taxonomy audit assets without requiring live AKShare, writing CSV, mutating taxonomy or combining SAMPLE and REAL evidence.
- The audit describes mapping coverage and ambiguity only; it is not an investment-quality score, formal industry classification, prediction or trading rationale.

## v3.8

- Evidence-backed theme observation traces.
- Added deterministic taxonomy and theme-definition fingerprints so each theme observation can point back to the exact configured mapping used for calculation.
- Added `src/theme_observation_evidence.py` and `tools/inspect_theme_evidence.py` for read-only inspection of theme calculation lineage across strict representative, representative and breadth modes.
- Theme evidence now exposes matched members, included/excluded rows, aggregation inputs, aggregate value, threshold mapping, derived state and SAMPLE/REAL source mode without reimplementing the theme formula separately.
- Historical evidence readiness now separates history span, intraday depth and coverage consistency instead of relying on one collapsed readiness label.
- Streamlit Theme Radar and Multi-Day tabs now include compact factual evidence panels; observation brief exports include a concise provenance footer.
- Smoke/runtime/cloud/release checks now verify theme evidence assets and SAMPLE evidence labeling without requiring live AKShare.
- This is analytical provenance, not model explainability, trading rationale, prediction or investment advice.

## v3.7

- Real historical coverage matrix and replay provenance.
- Added `src/history_evidence.py` to recover snapshot-level lineage from persisted CSV cache: file hash, schema fingerprint, provider/API metadata, data contract status, captured_time coverage and deterministic snapshot IDs.
- Added `tools/inspect_history_evidence.py` for read-only local inspection of REAL or SAMPLE CSV history, including optional coverage matrix and selected-date replay evidence.
- Multi-day theme snapshots now carry lightweight provenance attrs without changing theme calculations.
- Streamlit multi-day and data explanation panels now show read-only Historical Evidence summaries and captured_time coverage matrices for REAL and SAMPLE sources.
- Smoke/runtime/cloud/release checks now verify the historical evidence assets and SAMPLE replay provenance without requiring live AKShare or local real cache.
- Historical evidence is limited to lineage, coverage and replay provenance; it does not perform backtesting, return analysis, prediction or investment advice.

## v3.6

- Bounded real-data ingestion orchestration.
- Added `src/collection_policy.py` for lightweight local collection eligibility checks: trading-window style sessions, minimum interval and max attempts per session.
- Added `src/ingestion_metrics.py` for read-only collector audit-log metrics, write-intent success-rate semantics and real cache coverage labels.
- Added `tools/run_collection_session.py` as a finite manual runner around the existing one-shot collector; it does not create a scheduler, daemon or Streamlit loop.
- Smoke/runtime/cloud/release checks now verify collection policy, ingestion metrics and bounded runner assets without requiring live AKShare.
- Tests cover policy states, missing/malformed logs, success-rate denominator semantics, cache coverage labels and bounded runner stop conditions.
- CSV-first, public SAMPLE fallback, provider diagnostics, no-advice/no-prediction boundaries and ignored real cache/log files remain unchanged.

## v3.5

- AKShare live adapter resilience and schema-drift diagnostics.
- Added `src/providers/akshare_sector_flow.py` as the explicit AKShare/Eastmoney provider boundary for fetch diagnostics, controlled schema mapping, schema fingerprinting and normalization.
- `tools/probe_akshare.py` now reports AKShare version, provider API name, response type, row count, returned columns, schema fingerprint, normalization status and contract result without writing real cache files.
- Collector runs now preserve provider-level error categories such as `network_error`, `timeout_error`, `provider_parse_error`, `empty_response`, `schema_drift`, `normalization_error` and `contract_error` in results and audit logs.
- Added bounded retry support for transport/network/timeout failures only; schema drift, normalization and contract failures are not retried.
- Smoke/runtime/cloud/release checks now verify the provider adapter and probe assets without making CI depend on live AKShare.
- Tests cover known schemas, schema drift, ambiguous mappings, provider parse classification, retry behavior, probe JSON output and collector status mapping.

## v3.4

- Real cache catalog and freshness evidence.
- `src/snapshot_catalog.py` now exposes a richer real-cache summary with snapshot count, date coverage, latest path/date/time, modified time, empty/malformed file counts and staleness status.
- Added a read-only collector audit-log reader for `data/logs/collector_runs.jsonl`, including latest run status, status counts and malformed-line tolerance.
- The Streamlit data explanation tab now shows compact data-status evidence: current view status, real cache availability, freshness, collector latest status and public demo SAMPLE fallback note.
- `smoke_check.py` and `verify_runtime.py` report real cache coverage and collector audit-log visibility without requiring real cache or live AKShare in CI.
- Documentation explains how to inspect local real cache coverage and collector run status while keeping real CSV/logs ignored by Git.

## v3.3

- Real collector audit workflow.
- `tools/collect_market_snapshot.py` / `tools/collect_real_snapshot.py` now classify one-shot collector runs as `success`, `dry_run`, `no_network`, `fetch_error`, `empty_fetch`, `contract_error`, `duplicate_skipped` or `write_error`.
- Collector runs append a local JSONL audit record to `data/logs/collector_runs.jsonl` by default, with `--no-log` available for validation runs.
- `.gitignore`, release readiness, cloud preflight and smoke checks now cover collector log directories so runtime logs stay local.
- Tests cover mocked successful collection, dry-run safety, no-network behavior, empty/fetch/contract error classification, duplicate skip handling and audit log behavior.
- Public SAMPLE fallback, CSV-first storage, real cache ignore rules and no-advice/no-prediction boundaries remain unchanged.

## v3.2

- Real data ingestion and cache quality hardening.
- `src/transform.py` enriches normalized AKShare snapshots with practical provenance fields such as `data_mode=REAL`, provider, API name, fetched timestamp and rank value when available.
- `src/data_contracts.py` adds a real snapshot contract that is separate from SAMPLE checks, preventing SAMPLE/DEMO markers from leaking into real cache while keeping recommended fields as warnings.
- `tools/collect_market_snapshot.py` reports real snapshot contract status, provider, API name, trade date and data mode; `tools/collect_real_snapshot.py` provides a clearer local real-data collection entry point.
- `src/snapshot_catalog.py` exposes real cache provenance and freshness summary for tools and the Streamlit data explanation tab.
- 新增 `docs/REAL_DATA_INGESTION.md`，说明如何本地采集 AKShare 真实快照、缓存位置、校验方式、SAMPLE 区别和故障排查。
- 保持 SAMPLE 公开 fallback、CSV-first、本地真实缓存忽略规则和无投资建议边界不变。

## v3.1

- CI and operational quality hardening.
- 新增 `tools/quality_gate.py`，提供本地 pre-push 聚合检查，覆盖 pytest、compileall、release readiness、cloud preflight、public demo preflight、smoke check 和 runtime verification。
- 新增 `docs/OPERATIONS.md`，说明本地运行、质量门禁、GitHub Actions、Streamlit Cloud、public SAMPLE mode、常见故障排查和禁止提交文件。
- README 增加 CI badge、operations 文档入口和质量门禁命令。
- `release_check.py`、`cloud_preflight.py` 和 `smoke_check.py` 将 operations / quality gate 纳入公开发布资产检查。
- 保持 v3.0 数据契约、public demo runtime 和 Streamlit UI 行为不变，不新增产品功能。

## v3.0

- Engineering architecture hardening.
- 新增 `docs/ARCHITECTURE.md`，说明 Streamlit entry point、数据源、runtime profile、CSV/cache、SAMPLE、主题计算、UI、warehouse、简报和 release checks 的模块边界。
- 新增 `docs/DATA_FLOW.md`，说明 `LIVE / CACHE / HISTORY / SAMPLE / DEMO / EMPTY` 数据状态、CSV-first 流程、SAMPLE/真实缓存边界和数据可信口径。
- 新增 `src/data_contracts.py`，为 sector-flow snapshot 与 SAMPLE CSV 提供轻量 pandas 数据契约检查，并补充单元测试。
- `release_check.py`、`cloud_preflight.py`、`smoke_check.py` 和 `verify_runtime.py` 增加 SAMPLE 数据契约与架构文档检查。
- 新增简单 GitHub Actions CI 工作流，运行 pytest、compileall、release_check 和 cloud_preflight。
- 保持 v2.9 公开发布安全边界，不新增后端、不新增数据库类型、不改变主题计算或 Streamlit UI 主流程。

## v2.9

- Public release final audit.
- 新增 `docs/PUBLIC_RELEASE_AUDIT.md`，集中记录公开发布状态、验证矩阵、数据边界、GitHub 可见性检查、Streamlit Cloud 手动检查和 go/no-go 标准。
- `release_check.py` 增加 app version / CHANGELOG 一致性与 tracked forbidden files 检查，避免真实 CSV、SQLite、secrets 或虚拟环境文件进入公开发布。
- 新增 portfolio / interview / resume 文档包，为 GitHub 作品集、面试讲解和简历描述提供一致口径。
- 保持 v2.8 首屏导览和 v2.7 SAMPLE-first public demo 行为，不改变数据计算、不写 CSV、不写 SQLite。

## v2.8

- Public portfolio release presentation polish.
- 首页增加 compact demo guide，让外部访问者在首屏理解实时曲线、主题雷达、日内热点、多日趋势、持仓相关池和观察简报的阅读顺序。
- README 增强 “What to look at in the demo” 说明，继续强调 SAMPLE 是合成演示数据、不代表真实行情。
- PROJECT_BRIEF、VALIDATION、ROADMAP 和 release checklist 更新 v2.8 发布说明与手动检查重点。
- 保持 v2.7 Streamlit Cloud 首访 SAMPLE fallback，不改变数据计算、不写 CSV、不写 SQLite。

## v2.7

- Public deployment first-visit SAMPLE fallback.
- `runtime_profile.py` now defaults to SAMPLE + portfolio presentation when no local real cache is available but `sample_data/ticks` exists.
- Streamlit Cloud visitors no longer land on an EMPTY first screen when the repository includes reproducible SAMPLE data.
- Manual switch back to real/cache mode remains available and still shows EMPTY if no cache exists.
- README, VALIDATION, PROJECT_BRIEF and release checklist updated for the v2.7 public demo default behavior.

## v2.6

- Public demo runtime profile.
- 新增 `src/runtime_profile.py`，支持通过 `FUND_FLOW_PUBLIC_DEMO=1` 显式启用公开演示安全默认值。
- 新增 `tools/cloud_preflight.py`，检查 Streamlit Cloud / public demo 首次访问所需资产、runtime 默认值、README 链接和安全文案。
- app 在 public demo profile 下默认使用 SAMPLE 演示样例数据和作品集演示模式。
- `release_check.py`、`smoke_check.py` 和 `verify_runtime.py` 增加 runtime profile readiness 检查。
- README、VALIDATION、RELEASE_CHECKLIST、ROADMAP 和 PROJECT_BRIEF 增强 Streamlit Cloud demo 指引。

## v2.5

- Public portfolio README polish.
- 新增 `src/release_readiness.py`，用于发布前扫描公开资产、SAMPLE 说明、gitignore、Markdown 链接、本地路径、敏感词和动作性表达。
- 新增 `tools/release_check.py`，默认只打印 release readiness 结果，可选写入 `docs/release_readiness_report.md`。
- README 增强 public portfolio quick path、reproducible demo commands 和 release checks。
- `docs/screenshots/SCREENSHOT_GUIDE.md`、`docs/demo_briefs/README.md` 和 `docs/RELEASE_CHECKLIST.md` 增强为更可执行的发布材料。
- `smoke_check.py` 和 `verify_runtime.py` 增加 release readiness 检查。

## v2.4

- Theme history brief section.
- 新增 `src/theme_history_brief.py`，将 warehouse-powered theme history 转换为观察简报可用的中文摘要和 Markdown section。
- 观察简报 tab 增加 `包含 Warehouse 主题历史摘要` 开关；无 warehouse 时简报仍可正常生成。
- `tools/export_sample_brief.py` 默认使用 SAMPLE 数据和临时 warehouse 生成主题历史观察摘要，不读取 `data/ticks`，不写默认 `data/warehouse`。
- 静态 SAMPLE demo brief 增加主题历史观察摘要，继续明确 SAMPLE 合成演示数据不代表真实行情。
- `smoke_check.py` 和 `verify_runtime.py` 增加 theme history brief readiness 和 demo brief section 检查。

## v2.3

- Theme history visualization polish.
- 新增 `src/theme_history_viz.py`，将 warehouse-powered theme history 转换为折线图、热力矩阵、最新表现柱状图和 compact 状态时间线的数据。
- 多日趋势 tab 的 `Warehouse 主题历史观察（只读）` 增加 `主题历史图表` 区域。
- SAMPLE-only 图表明确标注为合成演示数据，不代表真实行情。
- `smoke_check.py` 和 `verify_runtime.py` 增加 theme history visualization readiness 检查。
- 新增 visualization validation tests，继续保持只读、CSV-first 和无投资建议边界。

## v2.2

- Warehouse-powered theme history aggregation.
- 新增 `src/theme_history.py`，从 warehouse 只读查询 sector history 并复用现有主题口径聚合主题历史。
- 多日趋势 tab 增加 `Warehouse 主题历史观察（只读）`，展示主题历史摘要、矩阵、状态时间线和质量报告。
- 支持 SAMPLE / LOCAL / ALL source_type 过滤，SAMPLE-only 明确标注为合成演示数据。
- `smoke_check.py` 和 `verify_runtime.py` 增加 theme history readiness 检查。
- 新增 theme history validation tests，保持 CSV-first 和只读边界。

## v2.1

- Read-only warehouse explorer.
- 新增 `src/warehouse_explorer.py`，提供 source_type、日期、captured_time 和板块样本只读查询。
- 新增 CSV-SQLite 一致性审计，用于判断 warehouse 是否需要从 CSV 手动重建。
- 数据说明 tab 增加 `Warehouse Explorer（只读）` 和 CSV-Warehouse consistency 面板。
- `smoke_check.py` 和 `verify_runtime.py` 增加 warehouse explorer readiness 检查。
- 新增 explorer validation tests，继续强调 CSV 是 source of truth，SQLite 只是可重建索引。

## v2.0

- Local SQLite warehouse foundation.
- 新增 `src/local_warehouse.py`，提供 SQLite 表初始化、CSV 行标准化、导入、防重、查询和审计。
- 新增 `tools/rebuild_local_warehouse.py`，从已有 CSV 手动重建本地 warehouse，不访问网络、不触发 AKShare、不写 CSV。
- 数据说明 tab 增加 `本地 SQLite Warehouse（可重建索引）` 状态和审计面板。
- `.gitignore` 增加 `data/warehouse/`、`*.sqlite`、`*.sqlite3` 和 `*.db`，避免提交本地数据库文件。
- `smoke_check.py` 和 `verify_runtime.py` 增加临时 warehouse readiness 检查。
- 新增 warehouse validation tests，保持 CSV-first 双轨设计。

## v1.9

- Polished observation brief templates.
- 新增 `src/brief_templates.py`，支持标准简报和作品集演示简报。
- 新增 `tools/export_sample_brief.py`，离线导出 SAMPLE demo brief，不访问网络，不读取或写入 `data/ticks`。
- 新增 `docs/demo_briefs/sample_observation_brief.md` 静态演示简报。
- 新增 `docs/RELEASE_CHECKLIST.md` 发布检查清单。
- `smoke_check.py` 和 `verify_runtime.py` 增加 demo brief readiness 与合规检查。

## v1.8

- Portfolio presentation mode.
- Unified data status badges for `LIVE / CACHE / HISTORY / SAMPLE / DEMO / EMPTY`.
- Demo walkthrough cards and screenshot checklist.
- Added `docs/screenshots/SCREENSHOT_GUIDE.md`.
- UI copy and layout polish for Streamlit portfolio presentation.
- README screenshot section now avoids broken image links.

## v1.7

- Local market snapshot collection script.
- 新增 `tools/collect_market_snapshot.py`，支持手动采集一次行业资金流快照、`--dry-run`、`--no-network` 和重复写入防护。
- 新增 `src/snapshot_quality.py`，支持 CSV 快照质量审计、坏 CSV 容错、缺字段检查和重复 `captured_time + sector_name` 检测。
- 数据说明 tab 增加 CSV 快照数据质量面板，区分本地真实缓存和 SAMPLE 样例数据。
- `smoke_check.py` 和 `verify_runtime.py` 增加 snapshot quality readiness 检查。
- 新增 snapshot governance tests，确保测试和运行时验证默认不访问网络。

## v1.6

- Fund / ETF theme exposure CSV template.
- 新增 `sample_data/fund_profiles/sample_fund_profiles.csv` 示例配置。
- 新增 `src/fund_profile_importer.py`，支持 CSV 读取、标准化、校验和主题雷达合并观察。
- 持仓相关池 tab 增加 CSV 配置来源、校验概览、Profile 概览、主题暴露明细和观察摘要。
- `smoke_check.py` 和 `verify_runtime.py` 增加 CSV profile readiness 检查。

## v1.5

- Streamlit Cloud deployment preparation.
- 新增 `.streamlit/config.toml` 深色主题和 headless 配置。
- 新增 `.streamlit/secrets.example.toml`，明确真实 secrets 不提交。
- README 增强首次运行、SAMPLE 模式和 Streamlit Cloud 部署说明。
- 首次访问时若真实缓存为空或抓取不可用，页面提示切换 SAMPLE 或 DEMO。
- `smoke_check.py` 和 `verify_runtime.py` 增加部署配置与 sample package 检查。

## v1.4

- Reproducible sample data mode.
- 新增 `sample_data/ticks/` 合成样例 CSV，方便无网络、无真实缓存时完整演示。
- 新增 `SAMPLE` 数据状态，明确区分样例数据、历史缓存、真实缓存、实时抓取和 DEMO。
- 新增 `tools/generate_sample_data.py`，可确定性重新生成样例数据包。
- SAMPLE 模式只读样例目录，不触发 AKShare，不写入 `data/ticks`。
- 优化首次运行体验：真实缓存为空时提示使用样例数据或 DEMO。

## v1.3

- Observation brief.
- Unified insight layer.
- Markdown export.
- Brief text validation.
- 简报整合主题雷达、日内热点、多日趋势、持仓相关池和主题覆盖审计。
- 简报只解释已展示或已保存的资金流状态，不触发 AKShare 抓取，不写入 CSV。

## v1.2

- Config-driven theme taxonomy via `config/theme_taxonomy.json`.
- 新增主题覆盖审计：覆盖率、高资金流未覆盖板块、重复映射 warning。
- 新增 watchlist / fund_profiles 主题一致性检查。
- 新增主题库说明和归并质量面板。
- `theme_pool` 和 `theme_concepts` 优先读取 taxonomy，并保留 fallback。

## v1.1

- Multi-day theme trend analysis.
- 新增每日主题快照构建：读取本地 CSV 日期的最后一个行业资金流快照。
- 新增多日趋势分类：多日偏强、改善、由弱转强、承压、走弱、分化。
- 新增多日趋势概览卡片、分区卡片和深色明细表。
- 多日趋势只分析本地已有 CSV，不触发 AKShare 抓取，不写入 CSV。

## v1.0

- Historical snapshot replay.
- 新增数据日期选择，可选择已有 CSV 日期只读回放。
- 新增 CSV 快照目录和数据质量标签。
- 新增 `HISTORY / EMPTY` 视图状态，避免历史缓存被误认为实时行情。
- 历史回放不会触发 AKShare 抓取，也不会写入 CSV。

## v0.9

- Intraday theme hotspot pool.
- 新增主题日内历史指标：日内变化、排名变化、流入/流出占比。
- 新增热点分类：持续流入、日内改善、由弱转强、持续流出、日内走弱、分化观察。
- 新增日内热点概览卡片、分区卡片和深色明细表。

## v0.8

- Manual fund profile configuration via `config/fund_profiles.json`.
- 新增持仓相关主题池。
- 新增基金影响摘要卡片。
- 明确手动主题配置不代表真实持仓，不读取真实账户。

## v0.7

- Low-frequency concept fund-flow assistance.
- 新增概念热点观察。
- 新增主题相关概念摘要。
- 新增手动刷新概念资金流入口。
- 明确行业资金流和概念资金流不直接相加。

## v0.6

- 页面改为 tabs：实时曲线、主题雷达、排行榜、数据说明。
- README 作品集化，补充架构、数据流、截图占位和验证方式。
- 新增数据可信面板，解释 `LIVE / CACHE / DEMO`。
- 新增 `CHANGELOG.md`、`ROADMAP.md`、`PROJECT_BRIEF.md`。
- 新增 `tools/smoke_check.py` 本地冒烟检查。

## v0.5

- 新增今日资金温度。
- 新增关注主题雷达。
- 新增核心/广度分歧提示。
- 新增 `watchlist.json` 自选关注主题。

## v0.4

- 新增 `strict_representative / 严格代表口径`。
- 新增 `theme_status` 资金流状态。
- 修复 DEMO 检测误判，真实板块名包含“模拟”不再被误判。

## v0.3

- 新增基金观察池。
- 支持 `representative / 代表口径` 和 `breadth / 广度观察`。

## v0.2

- 明确 `LIVE / CACHE / DEMO` 状态。
- AKShare 错误详情折叠展示。
- 排行榜深色化。

## v0.1

- 实时资金流曲线 MVP。
- 使用 AKShare 获取东方财富板块资金流数据。
- 使用 CSV 保存盘中快照。
