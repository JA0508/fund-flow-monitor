# CHANGELOG

## v2.7

- Public deployment first-visit SAMPLE fallback.
- `runtime_profile.py` now defaults to SAMPLE + portfolio presentation when no local real cache is available but `sample_data/ticks` exists.
- Streamlit Cloud visitors no longer land on an EMPTY first screen when the repository includes reproducible SAMPLE data.
- Manual switch back to real/cache mode remains available and still shows EMPTY if no cache exists.
- README, VALIDATION, PROJECT_BRIEF and release checklist updated for the v2.7 public demo default behavior.

## v2.6

- Public demo runtime profile.
- 新增 `src/runtime_profile.py`，支持通过 `FUND_FLOW_PUBLIC_DEMO=1` 显式启用公开演示安全默认值。
- 新增 `tools/cloud_preflight.py`，检查 Streamlit Cloud / public demo 首次访问所需资产、runtime 默认值、README 链接和安全文案。
- app 在 public demo profile 下默认使用 SAMPLE 演示样例数据和作品集演示模式。
- `release_check.py`、`smoke_check.py` 和 `verify_runtime.py` 增加 runtime profile readiness 检查。
- README、VALIDATION、RELEASE_CHECKLIST、ROADMAP 和 PROJECT_BRIEF 增强 Streamlit Cloud demo 指引。

## v2.5

- Public portfolio README polish.
- 新增 `src/release_readiness.py`，用于发布前扫描公开资产、SAMPLE 说明、gitignore、Markdown 链接、本地路径、敏感词和动作性表达。
- 新增 `tools/release_check.py`，默认只打印 release readiness 结果，可选写入 `docs/release_readiness_report.md`。
- README 增强 public portfolio quick path、reproducible demo commands 和 release checks。
- `docs/screenshots/SCREENSHOT_GUIDE.md`、`docs/demo_briefs/README.md` 和 `docs/RELEASE_CHECKLIST.md` 增强为更可执行的发布材料。
- `smoke_check.py` 和 `verify_runtime.py` 增加 release readiness 检查。

## v2.4

- Theme history brief section.
- 新增 `src/theme_history_brief.py`，将 warehouse-powered theme history 转换为观察简报可用的中文摘要和 Markdown section。
- 观察简报 tab 增加 `包含 Warehouse 主题历史摘要` 开关；无 warehouse 时简报仍可正常生成。
- `tools/export_sample_brief.py` 默认使用 SAMPLE 数据和临时 warehouse 生成主题历史观察摘要，不读取 `data/ticks`，不写默认 `data/warehouse`。
- 静态 SAMPLE demo brief 增加主题历史观察摘要，继续明确 SAMPLE 合成演示数据不代表真实行情。
- `smoke_check.py` 和 `verify_runtime.py` 增加 theme history brief readiness 和 demo brief section 检查。

## v2.3

- Theme history visualization polish.
- 新增 `src/theme_history_viz.py`，将 warehouse-powered theme history 转换为折线图、热力矩阵、最新表现柱状图和 compact 状态时间线的数据。
- 多日趋势 tab 的 `Warehouse 主题历史观察（只读）` 增加 `主题历史图表` 区域。
- SAMPLE-only 图表明确标注为合成演示数据，不代表真实行情。
- `smoke_check.py` 和 `verify_runtime.py` 增加 theme history visualization readiness 检查。
- 新增 visualization validation tests，继续保持只读、CSV-first 和无投资建议边界。

## v2.2

- Warehouse-powered theme history aggregation.
- 新增 `src/theme_history.py`，从 warehouse 只读查询 sector history 并复用现有主题口径聚合主题历史。
- 多日趋势 tab 增加 `Warehouse 主题历史观察（只读）`，展示主题历史摘要、矩阵、状态时间线和质量报告。
- 支持 SAMPLE / LOCAL / ALL source_type 过滤，SAMPLE-only 明确标注为合成演示数据。
- `smoke_check.py` 和 `verify_runtime.py` 增加 theme history readiness 检查。
- 新增 theme history validation tests，保持 CSV-first 和只读边界。

## v2.1

- Read-only warehouse explorer.
- 新增 `src/warehouse_explorer.py`，提供 source_type、日期、captured_time 和板块样本只读查询。
- 新增 CSV-SQLite 一致性审计，用于判断 warehouse 是否需要从 CSV 手动重建。
- 数据说明 tab 增加 `Warehouse Explorer（只读）` 和 CSV-Warehouse consistency 面板。
- `smoke_check.py` 和 `verify_runtime.py` 增加 warehouse explorer readiness 检查。
- 新增 explorer validation tests，继续强调 CSV 是 source of truth，SQLite 只是可重建索引。

## v2.0

- Local SQLite warehouse foundation.
- 新增 `src/local_warehouse.py`，提供 SQLite 表初始化、CSV 行标准化、导入、防重、查询和审计。
- 新增 `tools/rebuild_local_warehouse.py`，从已有 CSV 手动重建本地 warehouse，不访问网络、不触发 AKShare、不写 CSV。
- 数据说明 tab 增加 `本地 SQLite Warehouse（可重建索引）` 状态和审计面板。
- `.gitignore` 增加 `data/warehouse/`、`*.sqlite`、`*.sqlite3` 和 `*.db`，避免提交本地数据库文件。
- `smoke_check.py` 和 `verify_runtime.py` 增加临时 warehouse readiness 检查。
- 新增 warehouse validation tests，保持 CSV-first 双轨设计。

## v1.9

- Polished observation brief templates.
- 新增 `src/brief_templates.py`，支持标准简报和作品集演示简报。
- 新增 `tools/export_sample_brief.py`，离线导出 SAMPLE demo brief，不访问网络，不读取或写入 `data/ticks`。
- 新增 `docs/demo_briefs/sample_observation_brief.md` 静态演示简报。
- 新增 `docs/RELEASE_CHECKLIST.md` 发布检查清单。
- `smoke_check.py` 和 `verify_runtime.py` 增加 demo brief readiness 与合规检查。

## v1.8

- Portfolio presentation mode.
- Unified data status badges for `LIVE / CACHE / HISTORY / SAMPLE / DEMO / EMPTY`.
- Demo walkthrough cards and screenshot checklist.
- Added `docs/screenshots/SCREENSHOT_GUIDE.md`.
- UI copy and layout polish for Streamlit portfolio presentation.
- README screenshot section now avoids broken image links.

## v1.7

- Local market snapshot collection script.
- 新增 `tools/collect_market_snapshot.py`，支持手动采集一次行业资金流快照、`--dry-run`、`--no-network` 和重复写入防护。
- 新增 `src/snapshot_quality.py`，支持 CSV 快照质量审计、坏 CSV 容错、缺字段检查和重复 `captured_time + sector_name` 检测。
- 数据说明 tab 增加 CSV 快照数据质量面板，区分本地真实缓存和 SAMPLE 样例数据。
- `smoke_check.py` 和 `verify_runtime.py` 增加 snapshot quality readiness 检查。
- 新增 snapshot governance tests，确保测试和运行时验证默认不访问网络。

## v1.6

- Fund / ETF theme exposure CSV template.
- 新增 `sample_data/fund_profiles/sample_fund_profiles.csv` 示例配置。
- 新增 `src/fund_profile_importer.py`，支持 CSV 读取、标准化、校验和主题雷达合并观察。
- 持仓相关池 tab 增加 CSV 配置来源、校验概览、Profile 概览、主题暴露明细和观察摘要。
- `smoke_check.py` 和 `verify_runtime.py` 增加 CSV profile readiness 检查。

## v1.5

- Streamlit Cloud deployment preparation.
- 新增 `.streamlit/config.toml` 深色主题和 headless 配置。
- 新增 `.streamlit/secrets.example.toml`，明确真实 secrets 不提交。
- README 增强首次运行、SAMPLE 模式和 Streamlit Cloud 部署说明。
- 首次访问时若真实缓存为空或抓取不可用，页面提示切换 SAMPLE 或 DEMO。
- `smoke_check.py` 和 `verify_runtime.py` 增加部署配置与 sample package 检查。

## v1.4

- Reproducible sample data mode.
- 新增 `sample_data/ticks/` 合成样例 CSV，方便无网络、无真实缓存时完整演示。
- 新增 `SAMPLE` 数据状态，明确区分样例数据、历史缓存、真实缓存、实时抓取和 DEMO。
- 新增 `tools/generate_sample_data.py`，可确定性重新生成样例数据包。
- SAMPLE 模式只读样例目录，不触发 AKShare，不写入 `data/ticks`。
- 优化首次运行体验：真实缓存为空时提示使用样例数据或 DEMO。

## v1.3

- Observation brief.
- Unified insight layer.
- Markdown export.
- Brief text validation.
- 简报整合主题雷达、日内热点、多日趋势、持仓相关池和主题覆盖审计。
- 简报只解释已展示或已保存的资金流状态，不触发 AKShare 抓取，不写入 CSV。

## v1.2

- Config-driven theme taxonomy via `config/theme_taxonomy.json`.
- 新增主题覆盖审计：覆盖率、高资金流未覆盖板块、重复映射 warning。
- 新增 watchlist / fund_profiles 主题一致性检查。
- 新增主题库说明和归并质量面板。
- `theme_pool` 和 `theme_concepts` 优先读取 taxonomy，并保留 fallback。

## v1.1

- Multi-day theme trend analysis.
- 新增每日主题快照构建：读取本地 CSV 日期的最后一个行业资金流快照。
- 新增多日趋势分类：多日偏强、改善、由弱转强、承压、走弱、分化。
- 新增多日趋势概览卡片、分区卡片和深色明细表。
- 多日趋势只分析本地已有 CSV，不触发 AKShare 抓取，不写入 CSV。

## v1.0

- Historical snapshot replay.
- 新增数据日期选择，可选择已有 CSV 日期只读回放。
- 新增 CSV 快照目录和数据质量标签。
- 新增 `HISTORY / EMPTY` 视图状态，避免历史缓存被误认为实时行情。
- 历史回放不会触发 AKShare 抓取，也不会写入 CSV。

## v0.9

- Intraday theme hotspot pool.
- 新增主题日内历史指标：日内变化、排名变化、流入/流出占比。
- 新增热点分类：持续流入、日内改善、由弱转强、持续流出、日内走弱、分化观察。
- 新增日内热点概览卡片、分区卡片和深色明细表。

## v0.8

- Manual fund profile configuration via `config/fund_profiles.json`.
- 新增持仓相关主题池。
- 新增基金影响摘要卡片。
- 明确手动主题配置不代表真实持仓，不读取真实账户。

## v0.7

- Low-frequency concept fund-flow assistance.
- 新增概念热点观察。
- 新增主题相关概念摘要。
- 新增手动刷新概念资金流入口。
- 明确行业资金流和概念资金流不直接相加。

## v0.6

- 页面改为 tabs：实时曲线、主题雷达、排行榜、数据说明。
- README 作品集化，补充架构、数据流、截图占位和验证方式。
- 新增数据可信面板，解释 `LIVE / CACHE / DEMO`。
- 新增 `CHANGELOG.md`、`ROADMAP.md`、`PROJECT_BRIEF.md`。
- 新增 `tools/smoke_check.py` 本地冒烟检查。

## v0.5

- 新增今日资金温度。
- 新增关注主题雷达。
- 新增核心/广度分歧提示。
- 新增 `watchlist.json` 自选关注主题。

## v0.4

- 新增 `strict_representative / 严格代表口径`。
- 新增 `theme_status` 资金流状态。
- 修复 DEMO 检测误判，真实板块名包含“模拟”不再被误判。

## v0.3

- 新增基金观察池。
- 支持 `representative / 代表口径` 和 `breadth / 广度观察`。

## v0.2

- 明确 `LIVE / CACHE / DEMO` 状态。
- AKShare 错误详情折叠展示。
- 排行榜深色化。

## v0.1

- 实时资金流曲线 MVP。
- 使用 AKShare 获取东方财富板块资金流数据。
- 使用 CSV 保存盘中快照。
