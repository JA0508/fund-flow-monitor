# Public Repository Settings

Use this checklist before changing the GitHub repository from Private to Public.

## Recommended GitHub About

- Description: `A Streamlit dashboard for A-share sector/theme fund-flow observation, with reproducible sample-data demo mode.`
- Website: `https://fund-flow-monitor-ja0508.streamlit.app/`
- Visibility: keep Private until Streamlit Cloud deployment and safety checks are verified.

## Recommended Topics

- `streamlit`
- `plotly`
- `pandas`
- `akshare`
- `finance-dashboard`
- `data-visualization`
- `portfolio-project`

## README Checks

- README includes a live demo placeholder or the real Streamlit Cloud URL.
- README links only to files that exist in the repository.
- README screenshots are committed files under `docs/screenshots/`.
- README says SAMPLE is bundled synthetic demo data and does not represent real market quotes.
- README does not include local absolute paths, secrets, API keys, or private cache content.

## License

This repository includes an MIT License for public portfolio sharing. If you prefer not to grant reuse rights, remove `LICENSE` before making the repository public.

## Final Safety Checks

Run:

```bash
python tools/release_check.py
python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 python tools/cloud_preflight.py
git status --short
git check-ignore -v data/ticks/*.csv
git check-ignore -v data/warehouse/fund_flow.sqlite
git check-ignore -v .env
git check-ignore -v .venv/
git check-ignore -v .streamlit/secrets.toml
```

Do not make the repository public if real CSV snapshots, SQLite files, `.env`, `.venv/`, or Streamlit secrets appear in `git status`.
