# Screenshot Guide

This guide prepares reproducible screenshots for GitHub, Streamlit Cloud, and portfolio presentation.

## 1. Before Capturing

- Use `SAMPLE` data mode whenever possible. It is bundled synthetic data and keeps screenshots reproducible.
- Enable `作品集演示模式` in the sidebar to reduce debug noise while keeping data status warnings visible.
- Recommended browser width: 1440px or wider.
- Recommended setup command before screenshots: `python tools/release_check.py`.
- Do not show private `data/ticks` cache contents, `.env`, secrets, account data, or local absolute paths.
- `SAMPLE` data is synthetic and does not represent real market quotes.
- The project is for learning, visualization, and portfolio demonstration only. It does not predict future moves and does not provide investment advice.
- 中文边界说明：SAMPLE 是合成演示数据，不代表真实行情；截图文案不预测未来走势，不构成投资建议。

## 2. Recommended Screenshot Set

Use this numbered set when preparing a portfolio README or slide deck:

| File name | Target tab | Recommended mode | What to capture |
|---|---|---|---|
| `01_home_sample_status.png` | 实时曲线 | SAMPLE + 作品集演示模式 | Project intro, SAMPLE status badge, main curve |
| `02_theme_radar.png` | 主题雷达 | SAMPLE + 作品集演示模式 | Market temperature, watchlist radar, taxonomy status |
| `03_intraday_hotspots.png` | 日内热点 | SAMPLE + 作品集演示模式 | Intraday overview and hotspot sections |
| `04_multi_day_theme_history.png` | 多日趋势 | SAMPLE + 作品集演示模式 | Multi-day trend panel and theme history visuals |
| `05_warehouse_explorer.png` | 数据说明 | SAMPLE + 作品集演示模式 | Warehouse Explorer, CSV-Warehouse consistency, SAMPLE source |
| `06_observation_brief.png` | 观察简报 | SAMPLE + 作品集演示模式 | Brief template selector, theme history summary, disclaimer |
| `07_demo_brief_preview.png` | Markdown preview | SAMPLE demo brief | Static demo brief with theme history observation section |

## 3. Legacy Screenshot Slots

| File name | Target tab | Recommended mode | What to capture |
|---|---|---|---|
| `home_overview.png` | 实时曲线 | SAMPLE + 作品集演示模式 | Project intro, unified status badge, main curve |
| `theme_radar.png` | 主题雷达 | SAMPLE + 作品集演示模式 | Market temperature, watchlist radar, taxonomy status |
| `intraday_hotspots.png` | 日内热点 | SAMPLE + 作品集演示模式 | Intraday overview and hotspot sections |
| `multi_day_trends.png` | 多日趋势 | SAMPLE + 作品集演示模式 | Multi-day trend overview and sections |
| `theme_history_visuals.png` | 多日趋势 | SAMPLE + 作品集演示模式 | Warehouse theme history chart and SAMPLE explanation |
| `holding_pool.png` | 持仓相关池 | SAMPLE + 作品集演示模式 | Manual theme exposure and holding-related observation cards |
| `observation_brief.png` | 观察简报 | SAMPLE + 作品集演示模式 | Summary, key observations, disclaimer, Markdown download |
| `data_quality.png` | 数据说明 | SAMPLE + 作品集演示模式 | Local/SAMPLE quality cards and CSV snapshot quality area |
| `sample_mode.png` | 实时曲线 | SAMPLE + 作品集演示模式 | SAMPLE badge and synthetic data boundary note |

## 4. Per Screenshot Checklist

Each screenshot should include:

- A clear page or panel title.
- The `SAMPLE` or current data status badge.
- A visible note that SAMPLE is bundled synthetic demo data when using SAMPLE mode.
- No private local path, `.env`, secrets, account data, or real private cache content.
- No wording that suggests trading action, future prediction, or fund recommendation.

## 5. Capture Notes

- `theme_radar.png`: include the current theme mode and data status badge.
- `theme_history_visuals.png`: include the theme history chart area, source_type control, and SAMPLE synthetic-data notice.
- `observation_brief.png`: keep the disclaimer visible and ensure the Markdown download area is shown.
- `data_quality.png`: avoid showing private real-cache file paths if they contain local personal information.
- `sample_mode.png`: make the `SAMPLE` label and synthetic-data explanation visible.

## 6. Naming Rules

- Use lowercase English file names.
- Use underscores between words.
- Save files under `docs/screenshots/`.
- Future screenshot assets can be placed under `docs/screenshots/assets/` if the folder becomes large.
- Only reference screenshots in `README.md` after the file exists in the repository.

## 7. README Strategy

- Existing screenshots can be embedded directly in README.
- Missing screenshots should remain as text placeholders.
- Do not add broken Markdown image links.
