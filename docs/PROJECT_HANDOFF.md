# Fund Flow Monitor 项目交接

> 交接基线：`v3.18`，项目当前是 CSV-first 的 Streamlit 研究工具。本文用于说明项目已走到哪里、哪些边界不能破坏，以及后续应按什么顺序继续。

## 1. 当前定位

Fund Flow Monitor / 养基宝主题资金流雷达，服务于 A 股基金主题观察：将行业/概念资金流快照归并为半导体、AI 算力、新能源、医药、红利防御等基金用户可理解的主题状态。

它不是交易系统、荐基工具或预测模型。所有页面和导出物只描述已发生、已保存、可追溯的数据状态，不提供买卖建议，不预测未来走势。

## 2. 目前已完成什么

### 可用产品链路

- Streamlit 页面已包含实时曲线、主题雷达、日内热点、多日趋势、持仓相关池、观察简报、排行榜和数据说明。
- 主题雷达支持严格代表、代表、广度观察三种口径，并可追溯成员匹配、聚合输入、状态阈值和 taxonomy fingerprint。
- 用户可以在雷达查看“主题观察结论”，再展开技术证据；结论会同时说明成员覆盖、快照覆盖和限制。
- 观察简报可选择想复核的主题，并导出对应的主题结论、来源口径、动态/结构/关系证据以及限制说明。
- 若某个扩展证据层没有生成，页面和 Markdown 简报都会明确披露，不会把缺失证据伪装为支持性结论。

### 可信数据与研究基础

- `LIVE / CACHE / HISTORY / SAMPLE / DEMO / EMPTY` 的数据状态清晰分离。
- CSV 是唯一主数据来源；SQLite warehouse 只是可手动重建的只读索引。
- `sample_data/ticks/` 是公开、可复现的合成演示数据；`data/ticks/` 是本地 REAL 缓存，必须保持 Git 忽略。
- 历史回放、主题历史、warehouse explorer、数据质量、taxonomy 校准、动态/结构/关系/稳健性证据均建立在只读 CSV 证据之上。
- v3.15–v3.18 已把 provider contract、连续性分段、analytical eligibility 和 acquisition coverage 分开治理，避免“能读到 CSV”被误判为“已经具备严格多日研究资格”。

### 公开演示与工程保障

- `FUND_FLOW_PUBLIC_DEMO=1` 会优先进入 SAMPLE + 作品集演示模式；没有真实缓存或 warehouse 也能友好运行。
- CI、release check、cloud preflight、quality gate、数据契约和禁词检查已经存在。
- 公开 demo 不写 `data/ticks`、不自动创建 warehouse、不依赖 secrets。

## 3. 当前最重要的事实

项目的分析层已经比数据积累层成熟。下一阶段的核心不是增加图表或新模型，而是获得并沉淀足够的、可证明来源的 REAL 行业资金流快照。

当前版本对 REAL 多日证据使用保守门槛：

1. CSV 可读，只说明可以回放。
2. REAL observation 必须有 explicit verified primary-provider contract lineage，才可能进入 qualified analytical universe。
3. 物理采集还必须通过 provider-derived market-session date gate，并映射到预声明 acquisition cell。
4. 同一个 acquisition cell 内的重复采集仍然会保留，但不重复计算为新增时间覆盖。

因此，`3 个日期 × 每日 1 个快照` 可以形成“多日快照可读性”，但不自动等于 contract-qualified multi-day evidence。这个区分是项目最重要的可信度边界之一。

## 4. 数据与安全边界

| 范围 | 必须保持的规则 |
| --- | --- |
| REAL | 只能来自明确的 REAL 采集或受控离线导入，不能由 SAMPLE/DEMO 替代。 |
| SAMPLE | 只用于公开演示、测试和作品集；必须显著标记为合成数据，不代表真实行情。 |
| CSV | source of truth；任何新分析都应先从 CSV lineage 出发。 |
| SQLite | 只读、可重建索引；app 不能自动重建，也不能依赖其启动。 |
| Provider | 当前 runtime policy 为 `primary_only`；不可静默切换或混合 fallback。 |
| 网络 | CI、公开 demo 和测试不能依赖 live provider。 |
| 账户/持仓 | 不接券商账户，不读取个人真实持仓；fund profile CSV 只是主题暴露模板。 |

绝不能提交：`.env`、`.venv/`、`.streamlit/secrets.toml`、REAL `data/ticks/*.csv`、本地日志、SQLite/DB、Cookie、token、代理地址或浏览器 session 信息。

## 5. 运行与维护入口

### 公开演示

```bash
FUND_FLOW_PUBLIC_DEMO=1 .venv/bin/streamlit run app.py
```

此路径只应使用仓库内的 SAMPLE 数据，不需要真实缓存、warehouse 或 secrets。

### 日常质量检查

```bash
.venv/bin/python tools/quality_gate.py
.venv/bin/python tools/release_check.py
.venv/bin/python tools/cloud_preflight.py
FUND_FLOW_PUBLIC_DEMO=1 .venv/bin/python tools/cloud_preflight.py
```

### REAL 采集前的只读检查

```bash
.venv/bin/python tools/materialize_market_session_calendar.py --validate-only --json
.venv/bin/python tools/run_collection_session.py --no-network --no-log --max-runs 1 --json
.venv/bin/python tools/probe_akshare.py --json
.venv/bin/python tools/audit_provider_semantics.py --primary
.venv/bin/python tools/audit_analytical_eligibility.py --source REAL --json
.venv/bin/python tools/audit_evidence_accumulation.py --source REAL --json
```

正常 REAL 写入只应在用户明确授权、日期/时段 gate 通过、provider dry-run 正常时进行。详细步骤见 [REAL_ACCUMULATION_PROTOCOL.md](REAL_ACCUMULATION_PROTOCOL.md)。

## 6. 已知限制与真实阻塞点

1. **尚不应宣称已有 contract-qualified 多日 REAL 研究样本。** 真实采集必须先稳定通过 primary provider contract、日期 gate 和 acquisition cell 审计。
2. 免费 AKShare / Eastmoney 路径可能受 DNS、网络、接口 schema 或上游参数变化影响；一次 HTTP 成功不等于行业资金流语义或 contract 通过。
3. 市场日历是 provider-derived 的项目参考，不是交易所权威日历；覆盖范围外日期应保持 `market_calendar_unverified`。
4. offline REAL bundle importer 是 fail-closed 的导入路径，但 bundle manifest/SHA256 只能证明 bundle 内部一致，不能单独证明原始响应来自 Eastmoney。来源真实性仍依赖受控获取、可审计 provenance 和现有 validator。
5. 主题映射是项目定义的观察规则，不是官方行业分类；广度观察可能有重叠，不能解释为严格净流入。
6. 没有后台采集服务、云数据库或自动 scheduler；这是有意保持的 MVP 边界。

## 7. 后续迭代优先级

### P0：先完成 REAL evidence accumulation，不新增架构

目标是在明确授权的交易观察窗口内，按照既有协议获得第一批 explicit-verified REAL capture，并持续积累跨日期、跨 acquisition cell 的覆盖。

每次采集后都必须审计：

- physical capture count；
- qualified capture count；
- covered / missing acquisition cells；
- canonical observations 与 qualified canonical observations；
- qualified analytical readiness。

不要为了“让多日趋势可用”降低 provider contract、calendar gate 或 source separation。

### P1：把已获得的 REAL 证据转为更有用的研究工作流

在有足够 qualified REAL 历史后，优先做：

- 让主题观察结论明确引用所选日期、捕获时点、provider segment 和 qualified readiness；
- 把多日、结构、关系和稳健性证据按“可用 / 不足 / 排除原因”组织成更短的研究阅读路径；
- 让 Markdown 简报展示用户选择主题的完整证据链及数据限制；
- 为 theme taxonomy 的未匹配成员、重叠成员和 source-universe coverage 提供可操作的校准清单。

以上仍只解释历史证据，不引入预测、交易动作或基金推荐。

### P2：当 provider 问题有充分证据后，再处理 provider boundary

如果 primary AKShare path 再次异常，先做只读诊断：网络路径、请求参数、返回 row grain、行业 universe 语义、schema 和 contract。

仅当证据证明 provider contract 发生变化时，才考虑项目边界内的最小修复；不得直接修改 site-packages、硬编码本地代理、静默 fallback 或把股票 universe 当行业资金流写入 REAL CSV。

### P3：成熟后再考虑的方向

- 外部调度/运维说明与可控的低频采集运行方式；
- 更细的数据质量和异常归因；
- DuckDB 可选分析后端；
- FastAPI + React + ECharts 的独立产品化重构。

这些都不应抢在 qualified REAL evidence 之前。

## 8. 明确不建议继续做的事

- 为了展示效果继续堆图表、tab 或作品集文案；
- 新增第二个实时 provider 或自动 fallback；
- 让 warehouse 成为 app 的前提；
- 把 SAMPLE/DEMO 用作 REAL 缺失时的替代；
- 把 3 个可读日期直接写成严格多日研究结论；
- 接入账户、交易、预测或基金推荐能力；
- 在未验证 provider 语义时写入 REAL CSV。

## 9. 推荐的接手顺序

1. 阅读 [ARCHITECTURE.md](ARCHITECTURE.md)、[DATA_FLOW.md](DATA_FLOW.md) 和 [OPERATIONS.md](OPERATIONS.md)。
2. 在 SAMPLE 模式走一遍：主题雷达 → 主题证据 → 多日趋势 → 观察简报导出。
3. 跑 `tools/quality_gate.py`，确认本地工程基线。
4. 阅读 [REAL_ACCUMULATION_PROTOCOL.md](REAL_ACCUMULATION_PROTOCOL.md) 和 provider semantics 相关 CLI 输出。
5. 只有在明确授权的 eligible window，才进行最小 REAL dry-run / collection campaign；每次都以前后 evidence audit 作为完成标准。
6. REAL 证据积累后，再以真实用户问题推动 P1 的研究工作流改进。

## 10. 文档地图

- [README.md](../README.md)：公开入口、运行方式与边界。
- [ARCHITECTURE.md](ARCHITECTURE.md)：模块与职责。
- [DATA_FLOW.md](DATA_FLOW.md)：CSV、provider、主题和分析证据的数据流。
- [OPERATIONS.md](OPERATIONS.md)：日常运行、质量检查、CI 与 REAL 采集说明。
- [REAL_ACCUMULATION_PROTOCOL.md](REAL_ACCUMULATION_PROTOCOL.md)：qualified REAL evidence 的唯一操作协议。
- [PUBLIC_RELEASE_AUDIT.md](PUBLIC_RELEASE_AUDIT.md)：公开发布审计。
- [PORTFOLIO_PRESENTATION.md](PORTFOLIO_PRESENTATION.md)：面试/作品集说明，不应替代运行与证据文档。

## 11. 交接结论

项目已经越过“仅能公开演示”的阶段：它有可复现 SAMPLE 路径、可追溯主题观察、provider-aware lineage、qualified analytical readiness 和 acquisition coverage 治理。

但它尚未越过“真实数据证据积累完成”的阶段。下一位维护者最应该做的是用既有 fail-closed 协议积累和审计 REAL evidence，而不是绕过这些边界去制造更丰富的页面或更强的市场结论。
