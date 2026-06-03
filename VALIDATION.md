# Validation notes

## Runtime checks

Run:

```bash
python tools/verify_runtime.py
```

The script reports the active project path, Python version, AKShare version, whether `stock_sector_fund_flow_rank` exists, current CSV path and row count, snapshot count, latest captured time, latest inflow/outflow leaders, CSV snapshot catalog, DEMO contamination check, unit sanity check, and whether the current cache can build `strict_representative`, `representative`, and `breadth` fund observation theme snapshots.

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
- `数据说明` contains the data trust panel, `LIVE / CACHE / DEMO` explanation, theme mode explanation, watchlist instructions, and disclaimer.
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
  - `LIVE / CACHE / HISTORY / DEMO / EMPTY` explanation
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

## Data-source roadmap

This Streamlit MVP intentionally keeps the request strategy small:

- Current version only switches between `行业资金流` and `概念资金流`.
- It does not add high-frequency full crawling across industry, concept, region, today, 5-day, and 10-day dimensions.
- Next direction: backend full capture, frontend curated display.
- Recommended order: stabilize industry fund flow first, then gradually add concept fund flow, regional fund flow, 5-day, and 10-day views.

The reason is simple: the concept fund-flow endpoint can occasionally fail with proxy or upstream errors. Increasing request volume before the status and cache path are stable would make the dashboard less trustworthy.
