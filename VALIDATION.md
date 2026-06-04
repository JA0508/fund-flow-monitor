# Validation notes

## Runtime checks

Run:

```bash
python tools/verify_runtime.py
```

The script reports the active project path, Python version, AKShare version, whether `stock_sector_fund_flow_rank` exists, current CSV path and row count, snapshot count, latest captured time, latest inflow/outflow leaders, CSV snapshot catalog, DEMO contamination check, unit sanity check, and whether the current cache can build `strict_representative`, `representative`, and `breadth` fund observation theme snapshots.

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
