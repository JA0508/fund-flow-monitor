# Release Checklist

## 1. 本地验证

```bash
python -m pytest -q
python -m compileall app.py src tests tools
python tools/smoke_check.py
python tools/verify_runtime.py
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
git check-ignore -v .env
git check-ignore -v .streamlit/secrets.toml
git check-ignore -v .venv/
```

- 不提交 `data/ticks/*.csv`。
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
