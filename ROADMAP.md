# ROADMAP

Fund Flow Monitor 的长期目标是成为面向“养基宝 / 基金投资辅助”的 A 股主题资金流监测雷达。它不是交易系统，不做预测模型，也不提供投资建议。

## 1. 可信 Streamlit MVP

- 稳定行业资金流抓取。
- 明确 `LIVE / CACHE / HISTORY / SAMPLE / DEMO / EMPTY`。
- CSV 快照可追溯。
- 深色大屏、主题池、watchlist 和主题雷达可用。

## 2. 低频概念资金流

- 在行业资金流稳定后，低频接入概念资金流。
- 保持请求量克制，不做全量高频抓取。
- 继续保留缓存和错误降级。
- 概念资金流只作为主题热度和分化辅助观察，不与行业资金流直接相加。

## 3. 基金持仓 / ETF 成分映射

- v0.8 先实现本地手动配置版持仓相关池。
- 建立主题和基金持仓之间的解释层。
- 结合 ETF 成分、基金季报持仓和行业分类体系校准主题池。
- 避免把上下级板块重复计数解释为严格资金净流入。
- 不接真实券商账户，不读取个人真实持仓。

## 4. 持仓相关池

- 支持用户关注的基金或 ETF 组合。
- 根据持仓映射展示相关主题资金状态。
- 只做观察和解释，不做交易动作或预测结论。

## 5. 日内热点池

- v0.9 实现日内热点池 / 主题异动解释层。
- 从盘中快照中提取变化较明显的主题。
- 区分核心板块驱动和广度扩散。
- 保持中性文案，只描述资金流状态。

## 6. v1.0+ 产品化方向

- v1.0 完成历史快照回放、数据日期选择和 CSV 数据质量面板。
- v1.1 完成多日主题趋势 / 历史日期对比层。
- v1.2 完成主题库配置化、主题覆盖审计和归并质量面板。
- v1.3 完成主题观察简报、统一解释层和 Markdown 导出。
- v1.4 完成可复现演示模式、合成样例数据包和首次运行体验优化。
- v1.5 完成 Streamlit Cloud 部署准备、GitHub 作品集展示优化和首次访问体验打磨。
- v1.6 完成基金/ETF 主题暴露 CSV 模板导入、配置校验和持仓相关池增强。
- v1.7 完成本地数据采集脚本、CSV 快照治理和数据质量面板增强。
- v1.8 完成展示 polish、作品集演示模式、统一状态 badge 和 screenshot guide。
- v1.9 完成观察简报模板 polish、SAMPLE demo brief 离线导出和 release checklist。
- v2.0 完成本地 SQLite warehouse 基础、CSV-first 双轨存储和 warehouse 重建脚本。
- v2.1 完成 Warehouse Explorer、CSV-SQLite 一致性审计和只读历史查询面板。
- v2.2 完成 warehouse-powered 主题级历史聚合、多日趋势 tab 增强和主题历史质量报告。
- v2.3 完成主题级历史图表 polish、warehouse-powered 折线图、热力矩阵、最新表现柱状图和 compact 状态时间线。
- v2.4 完成主题历史接入观察简报、SAMPLE demo brief 主题历史摘要和 brief 合规增强。
- v2.5 完成 public portfolio release polish、README demo walkthrough、release readiness audit 和最终发布清单增强。
- v2.6 完成 public demo runtime profile、Streamlit Cloud 展示模式加固、cloud preflight 和云端首次访问体验优化。
- v2.7 完成 Streamlit Cloud 首访 SAMPLE fallback：无真实缓存但有 sample_data 时默认展示可复现 SAMPLE 演示。
- v2.8 完成 public portfolio presentation polish：首屏 demo guide、README 评审路径、项目简报和发布检查说明增强。
- v2.9 完成 public release final audit：版本一致性、tracked forbidden files、GitHub 可见性检查和公开发布 go/no-go 文档。
- v3.0 完成 engineering architecture hardening：架构文档、数据流文档、轻量数据契约、release/preflight 检查增强和 CI 基础工作流。
- v3.2 继续把真实 AKShare 采集、真实缓存质量和数据新鲜度可观测性作为本地真实数据主线。
- v3.3 完成本地真实采集器运行状态分类、JSONL 审计日志、no-network/no-log 安全校验和发布检查加固。
- v3.4 完成真实缓存目录证据层：cache coverage、freshness、empty/malformed 文件统计、collector audit-log 读取和数据说明 tab 可观测性增强。
- v3.5 完成 AKShare provider boundary 加固：显式 schema mapping、schema fingerprint、provider diagnostics、probe CLI、失败分类和 bounded retry。
- v3.6 完成 bounded real-data ingestion orchestration：采集窗口策略、有限次数 runner、collector audit metrics、cache coverage 标签和离线验证。
- v3.7 完成 real historical coverage matrix and replay provenance：从本地 CSV 恢复 snapshot lineage、schema fingerprint、文件 hash、captured_time 覆盖矩阵和 selected-date replay evidence。
- v3.8 完成 evidence-backed theme observation traces：主题库 fingerprint、主题定义 fingerprint、严格代表/代表/广度口径计算证据、状态阈值说明、历史覆盖三维状态和只读 CLI / Streamlit 证据面板。
- v3.9 完成 theme taxonomy calibration and overlap audit：主题成员角色、映射来源、别名歧义、跨主题重叠、SAMPLE / REAL source-universe coverage 和只读校准 CLI。
- v3.10 完成 theme dynamics cube and structural divergence：主题观测 fact grain、状态迁移路径、latest-per-date 演化、跨口径分歧和成员结构分歧的只读证据层。
- v3.11 完成 analytical grain integrity and canonical observation materialization：raw event grain、bucketed analytical grain、time-bucket collision audit、canonical bucket observations、scope alignment lineage 和只读 grain audit CLI。
- v3.12 完成 structural regime signatures and state-equivalent divergence：基于 canonical observations 的 headline/scope/member 结构签名、episode 切段、已观测结构切换和同 headline state 结构对照。
- v3.13 完成 cross-theme semantic-dynamic relationship evidence：基于 aligned canonical observations 的主题对齐、taxonomy overlap、headline agreement、structural-regime contrast 和 observed co-transition evidence。
- v3.14 完成 analytical robustness and specification sensitivity：分析规格身份、1/5/10 分钟 bucket 敏感性、materialization audit variant、证据充分度、阈值边界距离、日期集中度和 relationship ranking denominator guardrails。
- v3.15 完成 provider semantics registry and continuity gate：为 AKShare / Eastmoney 主路径建立语义契约、候选源可比性分类、连续性资格门禁、provider-aware lineage 和网络路径诊断。
- v3.16 完成 provider-contract-aware analytical continuity：canonical materialization、scope divergence、regime episodes、relationship alignment 和 robustness universe 保留 provider-contract continuity segment。
- v3.17 完成 contract-qualified analytical eligibility：把历史可读性与合格分析 readiness 分离，REAL qualified analytics 需要 explicit verified primary-provider lineage。
- v3.18 完成 qualified evidence accumulation protocol：物理采集事件、离线 market-session date gate、预声明采集框架、时间覆盖 cell、边际覆盖贡献和 coverage gap audit。
- 后续优先执行 bounded REAL accumulation protocol，在多个交易日积累 explicit-verified primary-provider captures，直到形成 contract-qualified multi-day evidence。
- v4.0 以后再考虑证据面板交互 polish、demo brief 图表截图引用、更细的数据质量规则、外部定时采集运维说明、DuckDB 可选分析后端。
- 在 Streamlit MVP 验证稳定后，再考虑 FastAPI + React + ECharts 产品化重构。
- 后端未来负责低频沉淀和统一 API。
- 前端未来负责主题雷达、曲线、热力图和交互展示。
