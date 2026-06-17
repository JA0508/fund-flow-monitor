# Portfolio Presentation

## Project Overview

Fund Flow Monitor / 养基宝主题资金流雷达 is a Streamlit dashboard that turns A-share sector and concept fund-flow snapshots into fund-user-friendly theme observations. It is designed for learning, visualization, and public portfolio review.

## Problem

Raw sector fund-flow lists are hard to evaluate from a fund-user perspective. They mix industries, concepts, duplicated hierarchy levels, cache states, and daily snapshots. A viewer needs a cleaner way to understand which themes are active, which data mode is being shown, and how reliable the displayed snapshot is.

## Product Value

The project adds an interpretation layer on top of raw industry/concept fund-flow data:

- Theme radar for fund-oriented sectors such as semiconductor chain, AI/TMT, new energy, medicine, consumer, dividend defense, military, and securities finance.
- Intraday hotspot and multi-day observation panels based on saved CSV snapshots.
- Holding-related pool based on local manual theme exposure configuration.
- Observation brief export and static SAMPLE demo brief.
- Clear data-state labels for LIVE / CACHE / HISTORY / SAMPLE / DEMO / EMPTY.

## Target Users

- Recruiters and interviewers evaluating a data application portfolio.
- Fund users who want to understand theme-level market observations.
- Developers reviewing a Streamlit + Plotly + pandas data product pattern.
- The project owner when preparing demos, screenshots, and interview explanations.

## Technical Stack

- Streamlit for UI and deployment.
- Plotly for dark financial charts.
- pandas for CSV snapshot processing.
- AKShare for optional local live data fetch.
- JSON / CSV configuration for theme taxonomy and fund exposure templates.
- SQLite as an optional rebuildable local query index.

## Data Architecture

The project is CSV-first:

- Local real snapshots live under ignored `data/ticks/*.csv`.
- Reproducible SAMPLE snapshots live under tracked `sample_data/ticks/*.csv`.
- SQLite warehouse is derived from CSV and can be rebuilt locally.
- Streamlit pages continue to work without SQLite.

## Engineering Architecture Notes

- Streamlit was chosen for fast product iteration and portfolio review: one deployable app can show data status, charts, tables, brief export, and release boundaries without adding a separate frontend/backend split too early.
- Public demo mode uses SAMPLE data because free live data and private local cache are not reliable assumptions for external reviewers.
- A production database was intentionally not made mandatory. CSV keeps data lineage inspectable during MVP development, and SQLite remains a local rebuildable query index.
- If the project later became production-grade, the natural path would be scheduled ingestion, stronger data quality rules, durable warehouse storage, API boundaries, monitoring, and compliance review.
- v3.0 adds architecture and data-flow documentation plus lightweight data contracts, improving maintainability without changing the app's user-facing calculation logic.

## Runtime and Data Modes

- `LIVE`: current successful fetch.
- `CACHE`: local real CSV cache.
- `HISTORY`: selected local real CSV replay.
- `SAMPLE`: bundled synthetic demo CSV.
- `DEMO`: in-memory UI demonstration data.
- `EMPTY`: no usable data for the selected path.

In public demo runtime, the app defaults to SAMPLE when no real cache exists and sample data is available.

## What to Review in the Demo

1. Start on the home / real-time curve page and confirm the data status badge.
2. Open Theme Radar to see how raw sectors become fund-oriented themes.
3. Open Intraday Hotspots to inspect same-day snapshot changes.
4. Open Multi-day Trends to see theme history and visualization panels.
5. Open Holding-related Pool to see manual fund theme exposure mapping.
6. Open Observation Brief to review Markdown export.
7. Open Data Explanation to inspect data trust, warehouse, and screenshot guidance.

## Safety Boundaries

- Not a brokerage or account tool.
- Does not read personal accounts or personal holdings.
- Does not provide trading actions.
- Does not predict future market movement.
- SAMPLE and DEMO do not represent real market quotes.

## Resume Bullet Drafts

- Built a Streamlit + Plotly A-share fund-flow dashboard that transforms sector snapshots into fund-oriented theme observations with reproducible SAMPLE demo mode.
- Designed CSV-first data governance with explicit LIVE / CACHE / HISTORY / SAMPLE / DEMO / EMPTY states and release-readiness checks for public portfolio deployment.
- Implemented theme radar, intraday hotspots, multi-day observations, holding-related pool, and Markdown observation brief export for a fund-flow visualization MVP.

## Interview Talking Points Summary

- The key design choice is trust: every view shows whether the data is live, cached, historical, synthetic sample, or empty.
- SAMPLE mode exists so public viewers can evaluate the app without real local cache or network-dependent upstream data.
- SQLite is intentionally secondary: it is a rebuildable query index, while CSV remains the source of truth.

## GitHub / About Short Description

`A Streamlit dashboard for A-share sector/theme fund-flow observation, with reproducible sample-data demo mode.`
