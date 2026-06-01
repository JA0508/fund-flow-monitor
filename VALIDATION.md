# Validation notes

## Runtime checks

Run:

```bash
python tools/verify_runtime.py
```

The script reports the active project path, Python version, AKShare version, whether `stock_sector_fund_flow_rank` exists, current CSV path and row count, snapshot count, latest captured time, latest inflow/outflow leaders, DEMO contamination check, unit sanity check, and whether the current cache can build `representative` and `breadth` fund observation theme snapshots.

DEMO contamination detection only checks mode-like fields: `source`, `sector_type`, `mode`, and `data_mode`. It intentionally does not inspect `sector_name`, because real Eastmoney sector names can contain words such as `模拟芯片设计`.

## Fund observation pool

The fund observation pool is not a simple sum of every related board.

- `representative / 代表口径`: uses primary sectors first, falling back to related sectors only when no primary sector is present. This lowers duplicate-counting risk from parent/child sector layers.
- `breadth / 广度观察`: uses primary and related sectors together to observe theme heat. The number can include overlapping sector definitions and should not be read as strict net inflow.

Current theme mapping is a lightweight rule layer. Later versions should calibrate it with fund holdings, ETF constituents, and a formal industry taxonomy.

The project is for learning, research, and visualization only. It is not investment advice.

## Data-source roadmap

This Streamlit MVP intentionally keeps the request strategy small:

- Current version only switches between `行业资金流` and `概念资金流`.
- It does not add high-frequency full crawling across industry, concept, region, today, 5-day, and 10-day dimensions.
- Next direction: backend full capture, frontend curated display.
- Recommended order: stabilize industry fund flow first, then gradually add concept fund flow, regional fund flow, 5-day, and 10-day views.

The reason is simple: the concept fund-flow endpoint can occasionally fail with proxy or upstream errors. Increasing request volume before the status and cache path are stable would make the dashboard less trustworthy.
