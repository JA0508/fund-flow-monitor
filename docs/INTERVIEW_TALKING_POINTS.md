# Interview Talking Points

## 30-Second Pitch

Fund Flow Monitor is a Streamlit portfolio project that turns A-share sector and concept fund-flow snapshots into fund-oriented theme observations. It shows real-time curves, theme radar, intraday hotspots, multi-day observations, holding-related pools, and Markdown briefs while clearly separating real cache, history, SAMPLE, DEMO, and empty states.

## 1-Minute Pitch

The project started from a fund-flow visualization idea and grew into a trust-focused Streamlit MVP. Raw industry fund-flow lists are difficult to read directly, so the app maps them into themes such as semiconductor chain, AI/TMT, new energy, medicine, consumer, dividend defense, military, and securities finance. It keeps CSV as the source of truth, supports a reproducible SAMPLE demo for public visitors, and uses optional SQLite only as a rebuildable query index. The app is for observation and visualization, not account access or trading decisions.

## 3-Minute Technical Explanation

The app fetches or reads sector fund-flow snapshots, normalizes them with pandas, and stores local real snapshots as CSV. The UI builds several interpretation layers from those snapshots: theme radar, intraday hotspots, multi-day trend summaries, holding-related pools, and observation briefs. For public demos, SAMPLE data under `sample_data/ticks` lets the app run without private local cache. The runtime profile detects public/demo-safe conditions and defaults to SAMPLE when appropriate. Release checks verify links, SAMPLE notices, gitignore safety, and unsafe wording before public sharing.

## Architecture Explanation

- Streamlit coordinates the UI and page state.
- pandas transforms CSV snapshots into normalized tables.
- Plotly renders dark financial charts.
- Theme taxonomy JSON defines fund-oriented mapping rules.
- CSV snapshots remain the primary data source.
- SQLite warehouse is optional and rebuildable from CSV.
- Lightweight data contracts validate the practical snapshot shape, especially SAMPLE CSV structure, without blocking valid local cache data unnecessarily.

## Engineering Architecture Tradeoff

I intentionally kept the project as a Streamlit MVP because the portfolio goal is to show the full observation workflow quickly: data-state trust, theme aggregation, visualization, brief export, and public-demo safety. Adding FastAPI, React, user login, or a production database too early would make the system look larger without proving more of the current product idea.

The current architecture is still modular: Streamlit is the UI shell, while data loading, runtime profile, CSV cataloging, theme mapping, warehouse querying, brief generation, release checks, and data contracts live in testable Python modules. If the project needed to scale, I would evolve it toward scheduled ingestion, a durable warehouse, API service boundaries, and a separate frontend.

## Data Pipeline Explanation

1. Optional AKShare fetch creates local real CSV snapshots.
2. SAMPLE CSV files provide a reproducible public demonstration path.
3. Normalization standardizes sector names, time points, and flow values.
4. Theme mapping converts sector rows into fund-oriented theme rows.
5. UI panels and briefs render observations from the active dataframe.

## Streamlit Cloud Deployment Explanation

Streamlit Cloud may not have local real cache and may not reliably reach external free data sources. The app handles this by defaulting to SAMPLE mode when no real cache exists but bundled SAMPLE data is present. This keeps the first visit useful while keeping SAMPLE clearly labeled as synthetic demonstration data.

## Why SAMPLE Mode Exists

SAMPLE mode makes the project reviewable without private files, credentials, or network-dependent live data. It also protects the public demo from showing empty screens while preserving the truth boundary that SAMPLE is not real market data.

## Data Trust Boundaries

The app explicitly labels LIVE, CACHE, HISTORY, SAMPLE, DEMO, and EMPTY. This prevents a viewer from confusing cached, historical, synthetic, or simulated data with current real market data.

## Tradeoffs

- CSV is simple and inspectable, but not a long-term production storage layer.
- Streamlit accelerates MVP delivery, but complex multi-user product architecture would eventually need a separate backend.
- Rule-based theme mapping is transparent, but it needs ongoing calibration against formal industry and fund-holding classifications.
- SAMPLE improves public demo reliability, but it cannot show real market behavior.

## What I Would Improve Next

- Add richer theme-level historical charts after more real local snapshots are collected.
- Improve taxonomy calibration using more formal sector classifications.
- Add more screenshot assets after the final live demo URL is stable.
- Consider DuckDB or a backend service only after the Streamlit MVP scope is fully validated.

## Common Interview Questions

### Why not make SQLite the main database?

CSV is easier to inspect, version around, and rebuild during MVP development. SQLite is useful as a local query index, but the project keeps CSV as the source of truth to avoid hiding data lineage.

### What does the project prove?

It proves the ability to design a trust-aware data dashboard: acquisition, normalization, theme mapping, visualization, documentation, public demo safety, and release checks are all connected.

### How do you prevent public demo confusion?

The UI shows data-state badges, SAMPLE notices, and non-real-data disclaimers. Public runtime defaults to SAMPLE only when appropriate, and the user can still switch modes manually.

### Is this a trading system?

No. It is an observation and visualization dashboard. It does not connect to brokerage accounts, does not read personal holdings, and does not provide trading actions or future market conclusions.
