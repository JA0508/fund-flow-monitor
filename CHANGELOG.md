# CHANGELOG

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
