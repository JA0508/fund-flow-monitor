# Release Checklist

## 1. 本地验证

```bash
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
python tools/rebuild_local_warehouse.py --include-sample --dry-run
```

## 2. SAMPLE Demo Brief 验证

```bash
python tools/export_sample_brief.py
```

- 检查 `docs/demo_briefs/sample_observation_brief.md` 存在。
- 确认简报包含 SAMPLE / 合成演示数据说明。
- 确认简报不包含买卖建议或预测语气。
- 确认简报不包含本地绝对路径或真实 `data/ticks` 私有缓存内容。

## 3. Git 安全检查

```bash
git status
git check-ignore -v data/ticks/*.csv
git check-ignore -v data/warehouse/fund_flow.sqlite
git check-ignore -v "*.sqlite"
git check-ignore -v "*.db"
git check-ignore -v .env
git check-ignore -v .streamlit/secrets.toml
git check-ignore -v .venv/
```

- 不提交 `data/ticks/*.csv`。
- 不提交 `data/warehouse/*.sqlite`。
- 不提交任何 `*.sqlite`、`*.sqlite3` 或 `*.db`。
- 不提交 `.env`。
- 不提交 `.streamlit/secrets.toml`。
- 不提交 `.venv/`、`__pycache__/`、`.pytest_cache/`。

## 4. Streamlit Cloud 检查

- `app.py` 位于仓库根目录。
- `requirements.txt` 位于仓库根目录。
- `.streamlit/config.toml` 已提交。
- `sample_data/ticks` 已提交。
- SAMPLE 模式可用。
- README 部署和首次访问说明清楚。

## 5. 作品集展示检查

- 开启作品集演示模式。
- 使用 SAMPLE 数据来源。
- 检查观察简报 tab。
- 检查截图指南 `docs/screenshots/SCREENSHOT_GUIDE.md`。
- 检查 README 无损坏图片链接。
- 检查 demo brief 链接可用。

## 6. 边界检查

- 不做交易。
- 不做买卖建议。
- 不预测未来走势。
- SAMPLE / DEMO 不代表真实行情。
- 观察简报只解释已展示或已缓存的资金流状态。
- SQLite warehouse 只是 CSV 可重建查询索引，不替代 CSV source of truth。

## 7. 可选 SQLite Warehouse 检查

```bash
python tools/rebuild_local_warehouse.py --include-sample --dry-run
python tools/rebuild_local_warehouse.py --include-sample
git status
```

- `--dry-run` 不应创建 SQLite 文件。
- `--include-sample` 可以创建 `data/warehouse/fund_flow.sqlite`。
- 创建后的 SQLite 文件必须被 `.gitignore` 忽略。
- 重建脚本不访问网络，不触发 AKShare，不写 `data/ticks` 或 `sample_data/ticks`。
- 可选打开数据说明 tab，检查 `Warehouse Explorer（只读）` 是否展示 SAMPLE warehouse。
- 确认 Explorer 只读查询，不自动重建 warehouse，不写 SQLite，不访问网络。
- 确认 `git status` 不出现 `data/warehouse/*.sqlite`、`*.db` 或真实 CSV。
