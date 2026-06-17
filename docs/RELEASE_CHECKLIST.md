# Release Checklist

Use this checklist before publishing the repository, updating a portfolio link, or deploying to Streamlit Cloud.

## 1. Automated Checks

```bash
python tools/cloud_preflight.py
python tools/release_check.py
python tools/smoke_check.py
python tools/verify_runtime.py
python -m pytest -q
python -m compileall app.py src tests tools
```

- `release_check.py` should report no errors.
- `release_check.py` should confirm APP_VERSION has a matching CHANGELOG entry.
- `release_check.py` should report no tracked forbidden files.
- `release_check.py` should report SAMPLE data contract status.
- `cloud_preflight.py` should confirm `docs/ARCHITECTURE.md` and `docs/DATA_FLOW.md` exist.
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
git check-ignore -v data/warehouse/fund_flow.sqlite
git check-ignore -v "*.sqlite"
git check-ignore -v "*.db"
git check-ignore -v .env
git check-ignore -v .venv/
git check-ignore -v .streamlit/secrets.toml
```

- Do not commit real `data/ticks/*.csv` snapshots.
- Do not commit `data/warehouse/*.sqlite`, `*.sqlite3`, or `*.db`.
- Do not commit `.env`, `.streamlit/secrets.toml`, `.venv/`, `__pycache__/`, or `.pytest_cache/`.
- `sample_data/ticks/*.csv` and demo brief files are public portfolio assets and should remain trackable.

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
