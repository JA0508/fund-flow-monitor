# fund-flow-monitor

本项目是一个本地可运行的 A 股行业/概念板块主力资金净流入实时动态监测大屏。第一版使用 Streamlit + Plotly 绘制深色资金流曲线，通过 AKShare 获取东方财富板块资金流排名数据，并把每次页面刷新时的快照保存为本地 CSV。

> 本项目仅用于学习和数据可视化，不提供自动交易、买卖建议或预测模型，不构成投资建议。

## 运行环境

- Python 3.10+
- macOS / Linux / Windows 均可
- 网络可访问 AKShare 依赖的东方财富接口

## 安装步骤

```bash
cd fund-flow-monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python tools/probe_akshare.py
streamlit run app.py
```

## 数据来源说明

第一版使用 AKShare 获取东方财富板块资金流数据：

- `ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")`
- `ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="概念资金流")`

免费数据源可能受上游接口变化、访问限制、非交易时间和网络环境影响。页面会明确显示数据源、更新时间、市场状态和 `LIVE` / `CACHE` / `DEMO` 数据状态。如果 AKShare 请求失败，页面会显示短错误提示并尽量读取本地 CSV 缓存继续展示，详细错误放在折叠区。

当前版本暂未处理中国法定节假日，仅按周一至周五和盘中时间段判断市场状态。

## 文件结构

```text
fund-flow-monitor/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
├── data/
│   ├── ticks/
│   └── demo/
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── data_source.py
│   ├── storage.py
│   ├── transform.py
│   ├── chart.py
│   ├── ui_components.py
│   ├── market_time.py
│   ├── theme_pool.py
│   └── utils.py
├── tests/
│   ├── test_transform.py
│   ├── test_market_time.py
│   └── test_theme_pool.py
└── tools/
    ├── probe_akshare.py
    └── verify_runtime.py
```

## 使用方式

启动后在侧边栏可选择：

- 展示模式：基金观察池 / 原始板块
- 主题口径：代表口径 / 广度观察，仅在基金观察池模式下显示
- 板块类型：行业资金流 / 概念资金流
- 刷新间隔：15 秒 / 30 秒 / 60 秒
- 净流入 Top N
- 净流出 Top N
- 是否启用 DEMO 模式

默认使用真实数据路径。DEMO 模式仅用于 UI 调试，页面会显示醒目的 `DEMO MODE - 当前为模拟数据，不是真实行情`，且不会写入真实 CSV。

数据状态分为三类：

- `LIVE`：本轮刷新 AKShare 抓取成功，并使用本轮快照。
- `CACHE`：本轮未成功获取实时数据，展示本地真实 CSV 缓存。
- `DEMO`：展示模拟数据，仅用于 UI 调试，不写入真实 CSV。

基金观察池会将相近行业/概念归并为基金主题，仅用于辅助观察。第一版支持：半导体/芯片链、AI算力/TMT、新能源链、红利防御、消费、医药、军工、证券金融。

基金观察池不是简单求和，而是提供两种口径：

- `representative / 代表口径`：优先使用主题核心板块计算主题主值；如果核心板块缺失，再使用相关板块 fallback。这个口径用于降低上下级板块重复计数风险。
- `breadth / 广度观察`：聚合核心板块和更多相关板块，用于观察主题热度。这个数值可能包含相关板块重叠，不代表严格净流入。

当前主题映射仍是轻量规则，后续需要结合基金持仓、ETF 成分、申万/中信等行业分类体系继续校准。

## 数据存储

每次抓取成功后会追加写入：

```text
data/ticks/sector_flow_YYYY-MM-DD.csv
```

保存字段包括交易日、捕获时间、板块类型、板块代码、板块名称、涨跌幅、主力净流入、主力净占比、超大单/大单/中单/小单净流入、龙头/主力净流入最大股和数据源。

## 常见问题

### 为什么非交易时间不动？

非交易时间不会强制抓取实时数据，会优先展示当天或最近缓存 CSV。页面会显示“非交易时间，展示最近缓存数据”，避免把缓存或模拟数据伪装成实时行情。

### 为什么 AKShare 报错？

可能是 AKShare 未安装、版本过旧、上游东方财富接口变化、网络限制或非交易时间接口返回异常。请先运行：

```bash
python tools/probe_akshare.py
```

### 为什么和截图数值不一样？

截图中的数据时间点、板块口径、数据源刷新频率可能不同。本项目以当前 AKShare 返回的东方财富板块资金流排名为准。

### 为什么基金观察池数值和原始行业榜不同？

基金观察池做了主题归并。代表口径优先看核心板块，广度观察会纳入更多相关板块，二者都不是基金净值，也不是严格行业资金流总量，只用于辅助观察主题热度和方向。

### 为什么普通基金不能做真实盘中净值？

普通公募基金净值通常在收盘后由基金公司和托管方核算发布，盘中没有严格意义上的实时真实净值。ETF 或场内基金可以观察交易价格，但那不是普通基金的最终单位净值。

## 后续升级计划

- 后端全量抓取，前端精选展示。
- 先做行业资金流稳定版，再逐步接入概念资金流、地域资金流、5日、10日。
- SQLite / PostgreSQL 存储
- FastAPI 后端服务
- React + ECharts 前端大屏
- WebSocket 实时推送
- 接入正式授权数据源
