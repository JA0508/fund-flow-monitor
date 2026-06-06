# Demo Briefs

本目录存放由 `sample_data/ticks` 合成演示数据生成的静态观察简报，用于 GitHub 作品集展示、面试讲解和离线预览。

- `sample_observation_brief.md` 基于 SAMPLE 合成演示数据生成，并包含主题历史观察摘要；它不代表真实行情。
- 这份简报展示项目如何整合主题雷达结果、主题历史观察摘要、持仓相关池观察、样本限制和免责声明。
- 简报仅用于学习研究、数据可视化和项目展示，不构成投资建议。
- 简报不预测未来走势，不包含交易功能。
- 不应手动加入真实行情结论、基金推荐、账户信息或买卖动作建议。

重新生成命令：

```bash
python tools/export_sample_brief.py
```

发布前检查：

```bash
python tools/release_check.py
```

`export_sample_brief.py` 只读取 SAMPLE 合成数据，并使用临时 warehouse 生成主题历史摘要；它不会访问 AKShare，不读取 `data/ticks`，也不写默认 `data/warehouse`。
