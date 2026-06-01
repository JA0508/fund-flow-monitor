from __future__ import annotations

import pandas as pd

from src.theme_radar import FORBIDDEN_ADVICE_WORDS


THEME_CONCEPT_KEYWORDS = {
    "半导体/芯片链": ["芯片", "半导体", "存储", "先进封装", "光刻机", "PCB", "第三代半导体"],
    "AI算力/TMT": ["人工智能", "AI", "算力", "CPO", "光模块", "数据中心", "云计算", "AIGC", "软件"],
    "新能源链": ["新能源", "锂电池", "储能", "光伏", "风电", "充电桩", "固态电池"],
    "红利防御": ["中字头", "央企改革", "高股息", "电力", "煤炭", "银行"],
    "消费": ["消费", "白酒", "食品饮料", "家电", "旅游", "免税"],
    "医药": ["医药", "创新药", "中药", "医疗器械", "生物医药"],
    "军工": ["军工", "航天", "航空", "低空经济", "商业航天"],
    "证券金融": ["证券", "金融", "互联网金融", "保险", "银行"],
}


def _concept_name_column(concept_df: pd.DataFrame) -> str:
    return "sector_name" if "sector_name" in concept_df.columns else "concept_name"


def _concept_status(value: float) -> str:
    if value >= 20:
        return "相关概念强流入"
    if 5 <= value < 20:
        return "相关概念流入"
    if -5 < value < 5:
        return "相关概念分歧"
    if -20 < value <= -5:
        return "相关概念流出"
    return "相关概念强流出"


def _concept_reason(theme_name: str, status: str, top_concepts: str) -> str:
    concepts = top_concepts or "相关概念"
    if status == "相关概念强流入":
        reason = f"{theme_name}：{concepts} 等相关概念资金流入较强，主题热度有所增强。"
    elif status == "相关概念流入":
        reason = f"{theme_name}：{concepts} 等相关概念资金小幅流入，主题热度略有支撑。"
    elif status == "相关概念强流出":
        reason = f"{theme_name}：{concepts} 等相关概念资金流出较多，概念侧资金承压。"
    elif status == "相关概念流出":
        reason = f"{theme_name}：{concepts} 等相关概念资金小幅流出，概念侧表现偏谨慎。"
    else:
        reason = f"{theme_name}：相关概念资金方向不突出，概念侧呈分歧状态。"
    for word in FORBIDDEN_ADVICE_WORDS:
        reason = reason.replace(word, "")
    return reason


def map_concepts_to_theme(concept_df: pd.DataFrame, theme_name: str) -> pd.DataFrame:
    if concept_df is None or concept_df.empty:
        return pd.DataFrame()
    keywords = THEME_CONCEPT_KEYWORDS.get(theme_name, [])
    if not keywords:
        return pd.DataFrame()
    df = concept_df.copy()
    name_col = _concept_name_column(df)
    names = df[name_col].fillna("").astype(str)
    mask = names.map(lambda name: any(keyword.lower() in name.lower() for keyword in keywords))
    return df[mask].copy()


def build_theme_concept_summary(concept_latest_df: pd.DataFrame, theme_names: list[str]) -> pd.DataFrame:
    rows = []
    for theme_name in theme_names:
        related = map_concepts_to_theme(concept_latest_df, theme_name)
        if related.empty:
            rows.append(
                {
                    "theme_name": theme_name,
                    "related_concept_count": 0,
                    "concept_net_inflow_billion": 0.0,
                    "top_concepts": "",
                    "concept_status": "相关概念分歧",
                    "concept_reason": f"{theme_name}：当前暂无匹配的概念资金流缓存，概念侧暂不参与判断。",
                }
            )
            continue
        name_col = _concept_name_column(related)
        related["main_net_inflow_billion"] = pd.to_numeric(related.get("main_net_inflow_billion"), errors="coerce")
        related = related.dropna(subset=["main_net_inflow_billion"])
        value = float(related["main_net_inflow_billion"].sum()) if not related.empty else 0.0
        status = _concept_status(value)
        top = (
            related.reindex(related["main_net_inflow_billion"].abs().sort_values(ascending=False).index)
            .head(5)[name_col]
            .fillna("")
            .astype(str)
            .tolist()
        )
        top_concepts = "，".join([item for item in top if item])
        rows.append(
            {
                "theme_name": theme_name,
                "related_concept_count": int(len(related)),
                "concept_net_inflow_billion": value,
                "top_concepts": top_concepts,
                "concept_status": status,
                "concept_reason": _concept_reason(theme_name, status, top_concepts),
            }
        )
    return pd.DataFrame(rows)
