# Validation notes

## Runtime checks

Run:

```bash
python tools/verify_runtime.py
```

The script reports the active project path, Python version, AKShare version, whether `stock_sector_fund_flow_rank` exists, current CSV path and row count, snapshot count, latest captured time, latest inflow/outflow leaders, DEMO contamination check, unit sanity check, and whether the current cache can build `strict_representative`, `representative`, and `breadth` fund observation theme snapshots.

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
- Page footer shows `养基宝主题资金流雷达 · v0.6 · Streamlit MVP`.
- No Streamlit default white dataframe should appear in the main dashboard.
- No trading or prediction wording should appear in user-facing text.

Project documentation checks:

- `README.md` is GitHub-ready and includes overview, features, screenshots placeholder, architecture, data flow, theme modes, watchlist, quick start, validation, limitations, and roadmap.
- `CHANGELOG.md` records v0.1 through v0.6.
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

## Data-source roadmap

This Streamlit MVP intentionally keeps the request strategy small:

- Current version only switches between `行业资金流` and `概念资金流`.
- It does not add high-frequency full crawling across industry, concept, region, today, 5-day, and 10-day dimensions.
- Next direction: backend full capture, frontend curated display.
- Recommended order: stabilize industry fund flow first, then gradually add concept fund flow, regional fund flow, 5-day, and 10-day views.

The reason is simple: the concept fund-flow endpoint can occasionally fail with proxy or upstream errors. Increasing request volume before the status and cache path are stable would make the dashboard less trustworthy.
