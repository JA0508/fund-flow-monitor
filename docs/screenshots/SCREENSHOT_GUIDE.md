# Screenshot Guide

This guide prepares reproducible screenshots for GitHub, Streamlit Cloud, and portfolio presentation.

## 1. Before Capturing

- Use `SAMPLE` data mode whenever possible. It is bundled synthetic data and keeps screenshots reproducible.
- Enable `作品集演示模式` in the sidebar to reduce debug noise while keeping data status warnings visible.
- Recommended browser width: 1440px or wider.
- Do not show private `data/ticks` cache contents, `.env`, secrets, account data, or local absolute paths.
- `SAMPLE` data is synthetic and does not represent real market quotes.
- The project is for learning, visualization, and portfolio demonstration only. It does not predict future moves and does not provide investment advice.

## 2. Recommended Screenshots

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

## 3. Capture Notes

- `theme_radar.png`: include the current theme mode and data status badge.
- `theme_history_visuals.png`: include the theme history chart area, source_type control, and SAMPLE synthetic-data notice.
- `observation_brief.png`: keep the disclaimer visible and ensure the Markdown download area is shown.
- `data_quality.png`: avoid showing private real-cache file paths if they contain local personal information.
- `sample_mode.png`: make the `SAMPLE` label and synthetic-data explanation visible.

## 4. Naming Rules

- Use lowercase English file names.
- Use underscores between words.
- Save files under `docs/screenshots/`.
- Only reference screenshots in `README.md` after the file exists in the repository.

## 5. README Strategy

- Existing screenshots can be embedded directly in README.
- Missing screenshots should remain as text placeholders.
- Do not add broken Markdown image links.
