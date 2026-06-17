# Operations Guide

This guide is for maintaining the public portfolio version of Fund Flow Monitor / 养基宝主题资金流雷达.

The project remains a Streamlit + CSV-first MVP. It is not a trading system, investment advisory product, account tool, or production financial data platform.

## Local Run

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

For a public-demo style local check:

```bash
FUND_FLOW_PUBLIC_DEMO=1 .venv/bin/streamlit run app.py
```

Expected public-demo behavior:

- Default data source is SAMPLE when sample CSV files are available.
- Default presentation mode is portfolio/demo mode.
- SAMPLE is always labeled as synthetic demo data.
- The app should not write `data/ticks` or create `data/warehouse/fund_flow.sqlite` just by opening the page.

## Pre-push Quality Gate

Run the full local quality gate before pushing a release-oriented change:

```bash
.venv/bin/python tools/quality_gate.py
```

It runs:

- `pytest`
- `compileall`
- `release_check.py`
- `cloud_preflight.py`
- public demo preflight with `FUND_FLOW_PUBLIC_DEMO=1`
- `smoke_check.py`
- `verify_runtime.py`

Useful variants:

```bash
.venv/bin/python tools/quality_gate.py --list
.venv/bin/python tools/quality_gate.py --stop-on-failure
.venv/bin/python tools/quality_gate.py --only release_check cloud_preflight
```

The quality gate should fail on real code or release-readiness errors. It should not require real private `data/ticks/*.csv`, secrets, or a local SQLite warehouse.

## GitHub Actions CI

The GitHub workflow is `.github/workflows/ci.yml`.

It uses a clean Ubuntu runner with Python 3.11 and runs:

```bash
python -m pytest -q
python -m compileall app.py src tests tools
python tools/release_check.py
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
```

CI should not use `.venv/bin/python`, local secrets, real local cache files, or network-sensitive live data checks.

If CI fails:

1. Open the failing workflow step.
2. Check whether the failure is dependency installation, tests, compile, release readiness, or cloud preflight.
3. Reproduce the same command locally with `.venv/bin/python`.
4. Fix code or docs issues before rerunning.
5. If a check is too brittle for clean runners, make the check degrade with a clear warning only when the missing resource is optional.

## Streamlit Cloud Deployment

Recommended public demo setting:

```text
FUND_FLOW_PUBLIC_DEMO=1
```

Deployment settings:

- Repository: `JA0508/fund-flow-monitor`
- Branch: `main`
- Main file: `app.py`

The app can run without `.streamlit/secrets.toml` for SAMPLE demo mode. Do not add real secrets to the repository.

If Streamlit Cloud shows `EMPTY` on first visit:

1. Confirm `sample_data/ticks/*.csv` exists in the deployed commit.
2. Confirm `FUND_FLOW_PUBLIC_DEMO=1` is set, or rely on the SAMPLE-first fallback when no local cache exists.
3. Confirm the sidebar data source can be switched back to SAMPLE.
4. Confirm no code path is trying to rebuild warehouse or write `data/ticks` during page load.

## Data Modes

- `LIVE`: real-time AKShare fetch for local use when available.
- `CACHE`: local real CSV cache from `data/ticks`.
- `HISTORY`: read-only historical CSV replay.
- `SAMPLE`: synthetic demo CSV from `sample_data/ticks`, suitable for public demos.
- `DEMO`: simulated fallback mode, not real market data.
- `EMPTY`: no usable local data for the selected mode.

SAMPLE and DEMO must never be described as real market data.

## Data Contracts

`src/data_contracts.py` provides lightweight CSV checks:

- Snapshot checks require only core columns needed by the app.
- SAMPLE checks additionally require SAMPLE markers.
- Recommended columns produce warnings, not hard failures.
- Missing directories produce readable warnings where appropriate.

The goal is to protect the public demo from broken sample files without blocking future real/cache CSV evolution.

## Files That Must Not Be Committed

Never commit:

- `.env`
- `.venv/`
- `.streamlit/secrets.toml`
- real `data/ticks/*.csv`
- `data/warehouse/*.sqlite`
- `*.sqlite`, `*.sqlite3`, `*.db`
- `.DS_Store`
- `__pycache__/`
- `.pytest_cache/`

Allowed public assets include:

- `.env.example`
- `data/ticks/.gitkeep`
- `sample_data/ticks/*.csv`
- `sample_data/fund_profiles/sample_fund_profiles.csv`
- `docs/demo_briefs/sample_observation_brief.md`

Before committing:

```bash
git status --short
git ls-files | grep -E "(\.env|\.venv|secrets.toml|data/ticks|\.sqlite|\.db|\.DS_Store)" || true
```

The only expected matches are `.env.example`, `data/ticks/.gitkeep`, and `sample_data/ticks/*.csv`.

## Updating SAMPLE Data Safely

SAMPLE data is public demo data. When changing it:

1. Keep it synthetic and clearly labeled as SAMPLE.
2. Do not copy private real cache files into `sample_data`.
3. Run:

```bash
.venv/bin/python tools/export_sample_brief.py
.venv/bin/python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 .venv/bin/python tools/cloud_preflight.py
.venv/bin/python tools/quality_gate.py
```

4. Open the app in SAMPLE mode and confirm the public demo still reads naturally.

## Manual Release Checks

After pushing:

- Check GitHub Actions is green.
- Open the Streamlit app in a private browser window.
- Confirm default SAMPLE / portfolio mode.
- Confirm the README links work.
- Confirm demo brief remains readable.
- Confirm no page or document contains local paths, secrets, trading actions, fund recommendations, or future prediction wording.
