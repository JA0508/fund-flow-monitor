# Public Release Audit

This audit summarizes the public-release readiness of `fund-flow-monitor` before changing the GitHub repository from Private to Public.

## Current Release Status

- App version: `v3.0`
- Release state: ready for public portfolio review after local validation and manual Streamlit Cloud checks.
- v2.9 finalized the public release audit; v3.0 adds architecture/data-flow documentation and lightweight SAMPLE data contract checks without changing user-facing calculation logic.
- Current public demo behavior: if no local real CSV cache exists but `sample_data/ticks` is available, the app defaults to SAMPLE demonstration data and portfolio presentation mode.
- Live demo URL: `https://fund-flow-monitor-ja0508.streamlit.app/`.

## Validated Checks

Run this validation set before publishing:

```bash
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
python tools/release_check.py
python tools/smoke_check.py
python tools/verify_runtime.py
python -m pytest -q
python -m compileall app.py src tests tools
```

Expected result:

- `release_check.py` reports no errors.
- `cloud_preflight.py` reports public demo readiness.
- SAMPLE snapshot CSVs pass the lightweight data contract check.
- Public demo mode defaults to SAMPLE when enabled.
- Tests and compile checks pass.
- GitHub Actions CI is available for pytest, compileall, release_check, and cloud_preflight on push or pull request.

## Public Demo Behavior

- SAMPLE is bundled synthetic demonstration data under `sample_data/ticks`.
- SAMPLE is reproducible and suitable for GitHub / Streamlit Cloud portfolio review.
- SAMPLE does not represent real market quotes.
- SAMPLE mode does not trigger AKShare and does not write `data/ticks`.
- Missing local real cache is not a failure in public demo mode; the app should remain useful through SAMPLE.

## Data Modes and Trust Boundaries

- `LIVE`: current successful data fetch.
- `CACHE`: local real CSV cache.
- `HISTORY`: selected local real CSV historical replay.
- `SAMPLE`: bundled synthetic demonstration CSV.
- `DEMO`: in-memory UI demonstration data.
- `EMPTY`: no usable cache or sample data for the selected path.

The UI must keep these modes visible and must not present SAMPLE or DEMO as real market data.

## Files That Must Not Be Tracked

Do not publish:

- `.env`
- `.venv/`
- `.streamlit/secrets.toml`
- real `data/ticks/*.csv`
- `data/warehouse/*.sqlite`
- `*.sqlite`, `*.sqlite3`, `*.db`
- generated cache folders such as `__pycache__/` and `.pytest_cache/`

Allowed public demo assets:

- `sample_data/ticks/*.csv`
- `sample_data/fund_profiles/sample_fund_profiles.csv`
- `docs/demo_briefs/sample_observation_brief.md`
- screenshots under `docs/screenshots/`

## GitHub Visibility Checklist

- GitHub description is filled.
- Topics are set.
- README live demo URL is either real and verified, or left as a placeholder.
- README screenshots point to existing committed files.
- `LICENSE` matches the intended public sharing policy.
- `docs/PUBLIC_REPO_SETTINGS.md` is reviewed.
- `git status --short` does not show sensitive or runtime data files.

Recommended description:

`A Streamlit dashboard for A-share sector/theme fund-flow observation, with reproducible sample-data demo mode.`

Recommended topics:

`streamlit`, `plotly`, `pandas`, `akshare`, `finance-dashboard`, `data-visualization`, `portfolio-project`

## Streamlit Cloud Manual Verification

After deployment, open the app and verify:

- First visit defaults to SAMPLE when no real cache exists.
- Portfolio presentation mode is active for public demo.
- SAMPLE / synthetic demonstration data notice is visible.
- Theme radar, intraday hotspots, multi-day trends, holding-related pool, observation brief, ranking, and data explanation tabs render.
- Warehouse panels do not require SQLite to exist.
- The page does not write `data/ticks` or `data/warehouse`.

## Known Limitations

- Free upstream data sources may be unstable in cloud environments.
- SAMPLE is synthetic and only demonstrates the workflow.
- CSV remains the source of truth for this MVP.
- SQLite warehouse is a local rebuildable query index, not a cloud database.
- Fund-related configuration is manual and does not read personal accounts or personal holdings.
- The project describes observed historical fund-flow states only; it does not provide trading actions or future market conclusions.

## Go / No-Go Criteria

Go public when:

- Validation commands pass.
- `release_check.py` reports no errors.
- Git status contains no real CSV, SQLite, secrets, virtualenv, or cache files.
- README links and screenshots render correctly on GitHub.
- Streamlit Cloud manual checks pass with SAMPLE visible.

Do not go public when:

- Real cache files, local database files, credentials, or secrets are tracked.
- README links or screenshots are broken.
- SAMPLE / DEMO boundaries are unclear.
- The app fails on first visit without local cache.
