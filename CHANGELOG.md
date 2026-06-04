# CHANGELOG

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
