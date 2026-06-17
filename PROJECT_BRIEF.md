# PROJECT BRIEF

## 项目背景

Fund Flow Monitor / 养基宝主题资金流雷达 是一个面向基金观察场景的 A 股主题资金流监测 MVP。普通基金净值通常无法盘中实时确认，但行业和主题资金流可以作为观察市场结构变化的一个数据维度。

## 解决的问题

原始行业/概念板块资金流列表数量多、层级杂、上下级口径容易混在一起。这个项目尝试把原始板块归并为“基金观察池”中的主题，让用户更快理解半导体、AI算力、新能源、红利防御、医药、证券金融等主题的资金流状态。

## 核心功能

- A 股行业/概念板块主力资金净流入盘中曲线。
- `LIVE / CACHE / HISTORY / SAMPLE / DEMO / EMPTY` 数据可信状态。
- CSV 快照沉淀和本地缓存降级。
- 基金观察池和三种主题口径。
- 今日资金温度。
- 关注主题雷达。
- 核心/广度分歧提示。
- 手动配置版持仓相关池。
- 日内热点池 / 主题异动解释层。
- 历史快照回放和 CSV 数据质量面板。
- 多日主题趋势 / 历史日期对比层。
- 主题库配置化和主题覆盖审计。
- 主题观察简报 / 统一解释层 / Markdown 导出。
- 观察简报模板 polish / SAMPLE demo brief 静态成果物。
- 可复现演示模式 / 合成样例数据包。
- Streamlit Cloud 部署准备和首次访问体验。
- 基金/ETF 主题暴露 CSV 模板和配置校验。
- 深色金融大屏 UI。

## 技术栈

- Python 3.10+
- Streamlit
- Plotly
- AKShare
- pandas
- streamlit-autorefresh
- CSV 本地存储
- pytest

## 数据可信设计

系统把页面展示状态拆分为五类：

- `LIVE`：本轮 AKShare 请求成功，并展示本轮刚抓取的数据。
- `CACHE`：本轮未成功获取实时数据或处于非交易时段，展示最近真实 CSV 缓存。
- `HISTORY`：选择历史缓存日期，只读展示本地 CSV，不触发抓取，不写入 CSV。
- `SAMPLE`：仓库内置合成样例 CSV，只读展示，不触发抓取，不写入真实缓存。
- `DEMO`：模拟数据，仅用于 UI 调试，不写入真实 CSV。
- `EMPTY`：暂无可用真实缓存，页面保持可用并提示等待抓取或启用 DEMO。

错误详情默认折叠，页面主区域只保留短提示，避免把网络异常当作主内容。

## 主题口径设计

- 严格代表口径：只使用主题核心板块的精确匹配，默认使用，降低上下级重复计数风险。
- 代表口径：优先核心板块，必要时使用近似板块补充。
- 广度观察：聚合更多相关板块，用于观察主题热度，可能包含重叠，不代表严格净流入。

主题状态和雷达文案只描述资金流状态，不做交易建议，不预测未来走势。

## 持仓相关池

v0.8 新增 `config/fund_profiles.json` 手动配置版持仓相关池。用户可以用本地 JSON 描述关注基金/ETF 与主题之间的暴露关系，系统再把这些主题映射到当前主题资金状态，生成基金摘要和主题暴露明细。

这不是读取真实账户，也不代表真实基金持仓。配置中的 `DEMO-` 代码仅用于本地观察示例。持仓相关池只做主题资金状态解释，不预测基金净值，不提供投资建议。

v1.6 增加 `sample_data/fund_profiles/sample_fund_profiles.csv` 主题暴露模板。CSV 只表达 profile 与主题之间的观察关系，不包含真实份额、金额、成本、收益或账户信息。页面会校验主题名是否注册在 `config/theme_taxonomy.json`，并把 CSV 暴露关系与当前主题雷达合并为观察摘要。CSV 导入不读取真实个人持仓，不接券商，不触发 AKShare，也不会写入 `data/ticks`。

## 日内热点池

v0.9 新增日内热点池。它基于本地 CSV 中同一交易日的多个 `captured_time` 快照，构建主题资金流历史，计算日内变化、排名变化、流入/流出时间占比，并把主题标记为持续流入、日内改善、由弱转强、持续流出、日内走弱或分化观察。

日内热点池只解释已经发生的日内资金流变化，不引入新数据源，不预测未来走势，不提供投资建议。快照数量不足时，页面会提示等待更多快照。

## 历史快照回放

v1.0 新增数据日期选择和历史快照回放。用户可以选择 `data/ticks/sector_flow_YYYY-MM-DD.csv` 中已有的缓存日期，回看该日期的实时曲线、主题雷达、日内热点、持仓相关池和排行榜。

历史回放是只读视图：不触发 AKShare 抓取，不写入 CSV，也不代表实时行情。数据说明页会展示 CSV 快照目录，包括行数、时间点数量、行业/概念行数、文件大小和质量标签，帮助判断某个日期是否适合回放。

## 多日主题趋势

v1.1 新增多日主题趋势。它基于本地 CSV 快照目录中的多个缓存日期，取每个日期最后一个行业资金流快照，构建主题跨日期指标，包括最早/最新金额、多日变化、流入/流出日期占比和最新状态。

多日趋势独立于当前单日历史回放日期，只分析本地已保存的历史资金流状态，不触发 AKShare 抓取，不写入 CSV，不预测未来走势，不提供投资建议。

## 主题库治理

v1.2 新增 `config/theme_taxonomy.json`，把主题名称、主题分组、核心行业、相关行业、概念关键词、别名、基金观察用途和重叠说明从代码中抽离为配置。`theme_pool.py` 和 `theme_concepts.py` 会优先读取主题库，加载失败时回退到内置默认规则，避免页面崩溃。

主题覆盖审计会基于当前最新行业资金流快照检查覆盖率、高资金流未覆盖板块、重复映射 warning，以及 watchlist / fund_profiles 与主题库的一致性。它只用于解释主题归并质量，不触发抓取，不写入 CSV，不预测未来走势。

## 观察简报

v1.3 新增观察简报。它把当前所选日期的主题雷达、日内热点、多日趋势、持仓相关池和主题覆盖审计整合为一份可读摘要，并支持 Markdown 下载。

观察简报不重新抓取数据，不写入 CSV，只复用页面中已经构建出的结果。简报会说明当前数据状态、主题口径、关键主题、样本不足情况、口径风险和数据源边界。导出前会做动作性表达检查，避免把观察说明写成操作建议。

v1.9 增强观察简报模板，支持标准简报和作品集演示简报。作品集演示简报更适合 GitHub 静态预览，会明确标注 SAMPLE 合成演示数据、不代表真实行情、不预测未来走势、不构成投资建议。

`tools/export_sample_brief.py` 可以离线读取 `sample_data/ticks` 生成 `docs/demo_briefs/sample_observation_brief.md`，用于作品集展示。该脚本不访问网络，不读取或写入 `data/ticks`，不会把真实本地缓存写入 docs。

`docs/RELEASE_CHECKLIST.md` 记录本地验证、demo brief、Git 安全、Streamlit Cloud 和作品集展示检查，帮助项目进入可发布状态。

## 可复现演示模式

v1.4 新增 `sample_data/ticks/` 合成样例数据包。新用户 clone 仓库后，即使没有网络、没有真实 `data/ticks` 缓存，也可以切换到 SAMPLE 模式体验主要功能。

SAMPLE 数据带有 `source=SAMPLE` / `data_mode=SAMPLE` 标记，只用于 UI 展示、学习研究和作品集演示。它不会触发 AKShare，不会写入真实 CSV，也不会被伪装成 LIVE、CACHE 或 HISTORY。

## 部署与首次访问

v1.5 增加 Streamlit Cloud 部署准备：`.streamlit/config.toml` 提供深色主题与 headless 配置，`.streamlit/secrets.example.toml` 只作为示例，真实 secrets 不提交。

首次访问时，如果没有真实缓存或 AKShare 暂不可用，页面会提示使用 SAMPLE 演示样例数据或 DEMO。这样公开部署环境也能展示完整产品能力，同时保持真实数据、历史缓存、样例数据和模拟数据之间的边界。

## 本地 CSV 快照治理

v1.7 增加 `tools/collect_market_snapshot.py` 手动采集脚本和 `src/snapshot_quality.py` 快照质量审计模块。采集脚本只手动运行一次，不是后台服务，不自动循环，不高频请求 AKShare；`--dry-run` 可检查抓取和快照质量但不写文件，`--no-network` 可离线检查脚本导入和参数。

v1.8 增加作品集演示模式、统一数据状态 badge 和截图指南。作品集演示模式只优化页面呈现密度，减少冗长调试信息对首屏的干扰，不改变主题计算结果，不触发 AKShare，不写入 CSV，也不会隐藏 SAMPLE / DEMO 的非真实行情提示。`docs/screenshots/SCREENSHOT_GUIDE.md` 用于指导 GitHub、Streamlit Cloud 和简历展示截图，避免暴露真实缓存、本地路径或 secrets。

数据说明页会展示本地真实缓存 `data/ticks` 与合成演示数据 `sample_data/ticks` 的文件数、行数、时间点数量、坏 CSV、缺字段和重复记录情况。质量面板只做文件和字段治理，不做投资判断。当前仍然是 CSV MVP，不是生产级数据平台。

## 本地 SQLite Warehouse

v2.0 增加本地 SQLite warehouse。它不是云数据库，也不是 CSV 的替代数据源，而是一个可以从 `data/ticks` 和 `sample_data/ticks` 重建的本地查询索引。

`tools/rebuild_local_warehouse.py` 可以手动把已有 CSV 导入 `data/warehouse/fund_flow.sqlite`。脚本不访问网络，不触发 AKShare，不写 CSV，不读取真实账户。默认只导入 SAMPLE 样例数据；只有显式传入 `--include-local` 才会导入本地真实缓存。

Streamlit app 没有 SQLite 也能运行。数据说明页只读取已有 warehouse 的状态、可用日期和审计结果，不会自动重建 warehouse。`data/warehouse/` 和 SQLite 文件被 `.gitignore` 忽略，避免把本地数据库提交到 GitHub。

v2.1 在此基础上增加 Warehouse Explorer 和 CSV-Warehouse 一致性审计。Explorer 只读取已有 SQLite 索引，展示 source_type 分布、日期、captured_time 和板块样本；一致性审计用于判断 CSV 目录与 warehouse 文件记录是否匹配。它不会访问网络，不会重建 warehouse，不会写 SQLite 或 CSV，也不会把 SAMPLE warehouse 解释成真实行情。

v2.2 增加 warehouse-powered 主题级历史聚合。系统从 warehouse 只读查询历史 sector flow，再复用主题库和既有主题口径聚合为主题历史矩阵、主题状态时间线和质量报告。该功能只解释已保存的历史资金状态，不预测未来走势，不做投资建议，也不替代 CSV 主数据链路。

v2.3 在主题历史聚合基础上增加可视化 polish：多日趋势 tab 中的 Warehouse 主题历史观察区域新增主题净流入折线图、主题历史热力矩阵、最新主题表现柱状图和 compact 状态时间线。图表只展示已导入 warehouse 的历史快照观察结果，不访问网络、不写 SQLite、不写 CSV；SAMPLE 图表明确标注为合成演示数据，不代表真实行情。

v2.4 将 warehouse-powered 主题历史轻量接入观察简报和 SAMPLE demo brief。观察简报可选包含主题历史观察摘要；静态 demo brief 默认使用 sample_data 和临时 warehouse 生成该 section，用于展示项目如何把历史 sector flow 转译为基金主题观察。该能力仍只描述已导入历史快照中的状态，不预测未来走势，不做投资建议，不读取真实账户，也不读取或写入真实 `data/ticks`。

## Public Portfolio Release

v2.5 聚焦公开发布质量，不新增业务分析功能。项目新增 release readiness audit，用于检查 README、docs、demo brief、截图指南、gitignore、Markdown 链接、本地路径、敏感词和动作性表达风险。

README、SAMPLE demo brief、screenshot guide 和 release checklist 现在形成一条可复现作品集路径：新用户可以使用 SAMPLE 数据、作品集演示模式、主题历史图表和观察简报理解项目能力。该发布路径仍然保持边界：SAMPLE 不代表真实行情，项目不预测未来走势，不做基金推荐，不提供交易功能。

## Public Demo Runtime

v2.6 聚焦 Streamlit Cloud 和公开展示环境的首次访问体验。项目新增 public demo runtime profile，可通过 `FUND_FLOW_PUBLIC_DEMO=1` 显式开启。开启后，页面默认使用 SAMPLE 合成演示数据和作品集演示模式，避免公开环境缺少真实缓存、AKShare 不稳定或 warehouse 未创建时出现不友好的空状态。

public demo profile 只是安全默认值，不是新数据源。CSV-first、SAMPLE 可复现、SQLite 可重建索引的边界不变；本地用户仍可手动选择真实数据 / 本地缓存模式。该模式不写 `data/ticks`，不自动创建 `data/warehouse`，不接真实账户，不读取真实持仓，不预测未来走势，不提供交易功能。

v2.7 进一步加固 Streamlit Cloud 首访体验：即使部署环境没有显式设置 `FUND_FLOW_PUBLIC_DEMO=1`，只要没有本地真实缓存且仓库内存在 `sample_data/ticks`，侧边栏也会默认选择 SAMPLE 和作品集演示模式。用户仍可手动切回真实数据 / 本地缓存模式；如果云端没有真实缓存，该模式继续显示 `EMPTY` 和可读提示，不会生成假数据。

## Public Portfolio Presentation Polish

v2.8 聚焦外部评审和公开作品集展示的第一屏理解成本。app 首页增加 compact demo guide，用简短卡片说明实时曲线、主题雷达、日内热点、多日趋势、持仓相关池和观察简报分别应该怎么看。

## Engineering Architecture Hardening

v3.0 聚焦工程架构成熟度，而不是新增业务功能。项目新增 `docs/ARCHITECTURE.md` 和 `docs/DATA_FLOW.md`，用于解释 Streamlit entry point、CSV-first 数据链路、SAMPLE 公开展示路径、runtime profile、可选 SQLite warehouse、主题计算层、简报层和 release checks 的边界。

同时新增 `src/data_contracts.py`，对 sector-flow snapshot 和 SAMPLE CSV 做轻量 pandas 数据契约检查。该检查用于提前发现列缺失、数值不可解析或 SAMPLE 标记缺失，不会把验证做得过度严格，也不会替代现有主题计算逻辑。

v3.0 仍然保持 Streamlit MVP 边界：不新增后端服务，不新增数据库类型，不接真实账户，不读取真实个人持仓，不预测未来走势，不提供交易功能。

这一轮不新增数据接口、不改变主题雷达/主题历史/观察简报计算，不写 CSV，不写 SQLite。README 和项目简报同步强化公开 demo 阅读路径、SAMPLE 边界、CSV-first 架构和非目标说明，帮助 GitHub 访客、Streamlit Cloud 访客、面试官或作品集评审快速理解项目价值。

v2.9 进一步补齐公开发布最终审计：`docs/PUBLIC_RELEASE_AUDIT.md` 记录公开发布状态、验证矩阵、数据边界、GitHub 可见性检查、Streamlit Cloud 手动检查和 go/no-go 标准。`release_check.py` 增加 APP_VERSION / CHANGELOG 一致性和 tracked forbidden files 检查，避免真实 CSV、SQLite、secrets 或虚拟环境文件进入公开发布。

v3.0 / v3.1 作为作品集材料准备阶段，新增 portfolio presentation、interview talking points、resume snippets 和 assets 占位说明。这些文档帮助公开评审理解项目，但不改变 app 数据链路、不新增后端、不改变 SAMPLE / CSV-first / SQLite 可重建索引边界。

## 当前限制

- 免费数据源可能受网络、代理和上游接口变化影响。
- 暂未处理中国法定节假日。
- CSV 适合 MVP，不适合长期生产环境。
- 主题映射仍是轻量规则，需要结合基金持仓、ETF 成分和行业分类体系校准。
- 持仓相关池仍是手动配置，不等同于正式基金持仓穿透。
- CSV 主题暴露模板只是作品集演示配置，不是账户持仓导入工具。
- 日内热点池依赖当天 CSV 快照数量，快照过少时只显示等待提示。
- 历史回放目前只支持单日 CSV 选择，暂未提供跨日趋势对比。
- 多日趋势目前只使用每个日期最后一个快照，暂未提供完整跨日期曲线图。
- 主题库仍是轻量规则，尚未接入正式行业分类体系和基金持仓穿透。
- 观察简报是规则化摘要，不调用大模型，不提供个性化投资结论。
- SAMPLE 样例数据是合成数据，仅用于演示和测试页面能力。
- 云端环境可能无法稳定访问免费数据源，公开演示时可使用 SAMPLE 模式。
- 本地采集脚本是手动一次性工具，暂未提供调度、失败重试、节流队列、数据库治理或正式数据血缘追踪。
- CSV 快照质量检查是基础审计，不替代生产级数据质量系统。
- SQLite warehouse 当前只作为可重建索引和基础查询层，核心页面仍走 CSV-first 数据流。

## 后续计划

- 低频接入概念资金流。
- 建立 ETF / 基金持仓映射。
- 增加持仓相关池。
- 增加日内热点池。
- 增加历史快照回放和数据质量面板。
- 增加多日主题趋势。
- 增加主题库治理和覆盖审计。
- 增加观察简报模板优化。
- 增加 SAMPLE demo brief 静态成果物。
- 保持演示样例数据可复现。
- 完善 Streamlit Cloud 和 GitHub 作品集展示。
- 增强基金/ETF 主题暴露模板和配置校验。
- 增强本地 CSV 快照治理和采集节流策略。
- 在 MVP 稳定后，再考虑 FastAPI + React + ECharts 重构。
