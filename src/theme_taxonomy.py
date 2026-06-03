from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


DEFAULT_THEME_TAXONOMY = {
    "taxonomy_name": "养基宝基金主题观察池",
    "version": "v1.2",
    "description": "本主题库用于将 A 股行业/概念资金流映射为基金观察主题，不代表正式行业分类或投资建议。",
    "themes": [
        {
            "theme_name": "半导体/芯片链",
            "theme_group": "科技成长",
            "description": "用于观察半导体、芯片设计、制造、封测、设备和电子链相关资金状态。",
            "primary_sectors": ["半导体"],
            "related_sectors": ["电子", "半导体设备", "半导体材料", "集成电路制造", "集成电路封测", "消费电子", "光学光电子", "印制电路板", "元件", "模拟芯片设计"],
            "concept_keywords": ["芯片", "半导体", "存储", "先进封装", "光刻机", "PCB", "第三代半导体"],
            "aliases": ["芯片链", "半导体链", "国产芯片"],
            "fund_use_case": "适合观察半导体主题基金、芯片 ETF、科技成长类基金的主题资金状态。",
            "overlap_notes": "广度观察可能包含电子、半导体和半导体设备等上下级板块，不能直接理解为严格净流入。",
        },
        {
            "theme_name": "AI算力/TMT",
            "theme_group": "科技成长",
            "description": "用于观察 AI、算力、计算机、通信、传媒和软件链相关资金状态。",
            "primary_sectors": ["计算机", "通信", "通信设备", "传媒"],
            "related_sectors": ["软件开发", "IT服务Ⅱ", "IT服务Ⅲ", "计算机设备", "通信服务", "通信网络设备及器件", "通信终端及配件", "通信工程及服务", "横向通用软件"],
            "concept_keywords": ["人工智能", "AI", "算力", "CPO", "光模块", "数据中心", "云计算", "AIGC", "软件"],
            "aliases": ["AI链", "算力链", "TMT"],
            "fund_use_case": "适合观察 AI、TMT、计算机、通信和科技主题基金的资金状态。",
            "overlap_notes": "广度观察可能同时包含计算机、软件开发和 IT 服务等上下级板块。",
        },
        {
            "theme_name": "新能源链",
            "theme_group": "新能源",
            "description": "用于观察电池、光伏、电力设备、储能等新能源链相关资金状态。",
            "primary_sectors": ["电池", "电力设备", "光伏设备"],
            "related_sectors": ["锂电池", "电池化学品", "光伏主材", "光伏辅材", "光伏发电", "光伏电池组件", "输变电设备", "电网设备", "储能"],
            "concept_keywords": ["新能源", "锂电池", "储能", "光伏", "风电", "充电桩", "固态电池"],
            "aliases": ["新能源", "光伏链", "锂电链"],
            "fund_use_case": "适合观察新能源主题基金、光伏 ETF、电池 ETF 相关主题资金状态。",
            "overlap_notes": "广度观察可能同时包含电力设备、电池、锂电池等上下级板块。",
        },
        {
            "theme_name": "红利防御",
            "theme_group": "稳健防御",
            "description": "用于观察银行、煤炭、电力、公用事业等红利与防御类主题资金状态。",
            "primary_sectors": ["银行", "煤炭", "电力", "公用事业"],
            "related_sectors": ["煤炭开采", "银行Ⅱ", "国有大型银行Ⅲ", "股份制银行Ⅲ", "火力发电", "水力发电", "电信运营商"],
            "concept_keywords": ["中字头", "央企改革", "高股息", "电力", "煤炭", "银行"],
            "aliases": ["高股息", "防御链", "红利资产"],
            "fund_use_case": "适合观察红利基金、高股息基金和防御风格基金相关主题资金状态。",
            "overlap_notes": "红利防御是风格型主题，不等同于单一行业。",
        },
        {
            "theme_name": "消费",
            "theme_group": "消费",
            "description": "用于观察食品饮料、白酒、家电、零售和旅游消费相关资金状态。",
            "primary_sectors": ["食品饮料"],
            "related_sectors": ["白酒Ⅱ", "白酒Ⅲ", "非白酒", "白色家电", "黑色家电", "小家电", "一般零售", "商贸零售", "旅游零售Ⅱ", "旅游零售Ⅲ"],
            "concept_keywords": ["消费", "白酒", "食品饮料", "家电", "旅游", "免税"],
            "aliases": ["大消费", "消费链"],
            "fund_use_case": "适合观察消费主题基金、食品饮料基金和白酒相关基金的主题资金状态。",
            "overlap_notes": "消费主题可能覆盖行业较宽，广度观察不代表严格净流入。",
        },
        {
            "theme_name": "医药",
            "theme_group": "医药健康",
            "description": "用于观察医药生物、医疗器械、创新药、中药等医药健康主题资金状态。",
            "primary_sectors": ["医疗器械", "医药生物"],
            "related_sectors": ["生物制品", "其他生物制品", "中药Ⅱ", "中药Ⅲ", "医疗服务", "化学制药", "其他医疗服务"],
            "concept_keywords": ["医药", "创新药", "中药", "医疗器械", "生物医药"],
            "aliases": ["医药健康", "创新药链"],
            "fund_use_case": "适合观察医药主题基金、医疗 ETF 和创新药相关基金的资金状态。",
            "overlap_notes": "医药主题内部子行业分化可能较明显。",
        },
        {
            "theme_name": "军工",
            "theme_group": "高端制造",
            "description": "用于观察国防军工、航空航天和军工电子相关资金状态。",
            "primary_sectors": ["国防军工"],
            "related_sectors": ["航天装备Ⅱ", "航天装备Ⅲ", "航空装备Ⅱ", "航空装备Ⅲ", "军工电子Ⅱ", "军工电子Ⅲ"],
            "concept_keywords": ["军工", "航天", "航空", "低空经济", "商业航天"],
            "aliases": ["国防军工", "军工链"],
            "fund_use_case": "适合观察军工主题基金和高端制造相关基金的资金状态。",
            "overlap_notes": "军工与电子、通信等主题可能存在交叉。",
        },
        {
            "theme_name": "证券金融",
            "theme_group": "金融",
            "description": "用于观察证券、保险、多元金融等非银金融相关资金状态。",
            "primary_sectors": ["证券Ⅱ", "证券Ⅲ"],
            "related_sectors": ["保险Ⅱ", "保险Ⅲ", "多元金融", "银行"],
            "concept_keywords": ["证券", "金融", "互联网金融", "保险", "银行"],
            "aliases": ["非银金融", "券商金融"],
            "fund_use_case": "适合观察证券 ETF、金融主题基金和非银金融相关主题资金状态。",
            "overlap_notes": "金融主题和红利防御可能在银行方向上存在交叉。",
        },
    ],
}


def _as_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def load_theme_taxonomy(path: str = "config/theme_taxonomy.json") -> dict:
    target = Path(path)
    if not target.exists():
        taxonomy = copy.deepcopy(DEFAULT_THEME_TAXONOMY)
        taxonomy["_load_warning"] = f"{path} 不存在，已使用内置默认主题库。"
        return taxonomy
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        taxonomy = copy.deepcopy(DEFAULT_THEME_TAXONOMY)
        taxonomy["_load_warning"] = f"{path} 读取失败，已使用内置默认主题库：{exc}"
        return taxonomy
    if not isinstance(data, dict):
        taxonomy = copy.deepcopy(DEFAULT_THEME_TAXONOMY)
        taxonomy["_load_warning"] = f"{path} 格式不是 JSON object，已使用内置默认主题库。"
        return taxonomy
    return data


def get_taxonomy_themes(taxonomy: dict) -> list[dict]:
    themes = taxonomy.get("themes", []) if isinstance(taxonomy, dict) else []
    return [theme for theme in themes if isinstance(theme, dict)]


def get_theme_names(taxonomy: dict) -> list[str]:
    return [str(theme.get("theme_name")).strip() for theme in get_taxonomy_themes(taxonomy) if str(theme.get("theme_name", "")).strip()]


def validate_theme_taxonomy(taxonomy: dict) -> list[str]:
    warnings = []
    if not isinstance(taxonomy, dict):
        return ["taxonomy 不是 JSON object。"]
    if not taxonomy.get("taxonomy_name"):
        warnings.append("taxonomy_name 不存在。")
    themes = get_taxonomy_themes(taxonomy)
    if not themes:
        warnings.append("themes 不存在或为空。")
    names = []
    sector_theme_counter: dict[str, set[str]] = defaultdict(set)
    for idx, theme in enumerate(themes, start=1):
        name = str(theme.get("theme_name", "")).strip()
        if not name:
            warnings.append(f"第 {idx} 个主题 theme_name 为空。")
        else:
            names.append(name)
        for field in ("primary_sectors", "related_sectors", "concept_keywords"):
            if not isinstance(theme.get(field), list):
                warnings.append(f"{name or idx}: {field} 不是 list。")
        for sector in _as_list(theme.get("primary_sectors")) + _as_list(theme.get("related_sectors")):
            sector_theme_counter[sector].add(name)
    duplicates = [name for name, count in Counter(names).items() if count > 1]
    for name in duplicates:
        warnings.append(f"重复 theme_name: {name}。")
    crowded = sorted(sector for sector, theme_names in sector_theme_counter.items() if len(theme_names) > 2)
    for sector in crowded:
        warnings.append(f"{sector}: 同一个 sector 出现在超过 2 个主题中。")
    load_warning = taxonomy.get("_load_warning")
    if load_warning:
        warnings.insert(0, str(load_warning))
    return warnings


def build_theme_definition_table(taxonomy: dict) -> pd.DataFrame:
    rows = []
    for theme in get_taxonomy_themes(taxonomy):
        rows.append(
            {
                "theme_name": theme.get("theme_name", ""),
                "theme_group": theme.get("theme_group", ""),
                "description": theme.get("description", ""),
                "primary_sectors": "，".join(_as_list(theme.get("primary_sectors"))),
                "related_sectors": "，".join(_as_list(theme.get("related_sectors"))),
                "concept_keywords": "，".join(_as_list(theme.get("concept_keywords"))),
                "aliases": "，".join(_as_list(theme.get("aliases"))),
                "fund_use_case": theme.get("fund_use_case", ""),
                "overlap_notes": theme.get("overlap_notes", ""),
            }
        )
    return pd.DataFrame(rows)


def build_sector_to_theme_map(taxonomy: dict) -> pd.DataFrame:
    rows = []
    for theme in get_taxonomy_themes(taxonomy):
        theme_name = str(theme.get("theme_name", "")).strip()
        theme_group = str(theme.get("theme_group", "")).strip()
        for sector in _as_list(theme.get("primary_sectors")):
            rows.append({"sector_name": sector, "theme_name": theme_name, "sector_role": "primary", "theme_group": theme_group})
        for sector in _as_list(theme.get("related_sectors")):
            rows.append({"sector_name": sector, "theme_name": theme_name, "sector_role": "related", "theme_group": theme_group})
    return pd.DataFrame(rows, columns=["sector_name", "theme_name", "sector_role", "theme_group"])


def build_concept_keyword_table(taxonomy: dict) -> pd.DataFrame:
    rows = []
    for theme in get_taxonomy_themes(taxonomy):
        theme_name = str(theme.get("theme_name", "")).strip()
        theme_group = str(theme.get("theme_group", "")).strip()
        for keyword in _as_list(theme.get("concept_keywords")):
            rows.append({"theme_name": theme_name, "concept_keyword": keyword, "theme_group": theme_group})
    return pd.DataFrame(rows, columns=["theme_name", "concept_keyword", "theme_group"])


def taxonomy_to_theme_definitions(taxonomy: dict) -> dict[str, dict[str, list[str]]]:
    definitions = {}
    for theme in get_taxonomy_themes(taxonomy):
        name = str(theme.get("theme_name", "")).strip()
        if not name:
            continue
        definitions[name] = {
            "primary_sectors": _as_list(theme.get("primary_sectors")),
            "related_sectors": _as_list(theme.get("related_sectors")),
        }
    return definitions


def taxonomy_to_concept_keywords(taxonomy: dict) -> dict[str, list[str]]:
    return {
        str(theme.get("theme_name", "")).strip(): _as_list(theme.get("concept_keywords"))
        for theme in get_taxonomy_themes(taxonomy)
        if str(theme.get("theme_name", "")).strip()
    }


def audit_theme_name_consistency(
    taxonomy: dict,
    watchlist_themes: list[str],
    fund_profile_themes: list[str],
) -> dict:
    taxonomy_names = set(get_theme_names(taxonomy))
    watchlist_set = {str(theme).strip() for theme in watchlist_themes if str(theme).strip()}
    fund_set = {str(theme).strip() for theme in fund_profile_themes if str(theme).strip()}
    missing_watchlist = sorted(watchlist_set - taxonomy_names)
    missing_funds = sorted(fund_set - taxonomy_names)
    used = watchlist_set | fund_set
    unused = sorted(taxonomy_names - used)
    if missing_watchlist or missing_funds:
        label = "存在未注册主题"
        reason = "watchlist 或 fund_profiles 中存在未纳入主题库的主题名称，需要人工校准。"
    elif unused:
        label = "存在未使用主题"
        reason = "主题库中有部分主题当前未被 watchlist 或 fund_profiles 使用。"
    else:
        label = "全部一致"
        reason = "watchlist 与 fund_profiles 中的主题名称均已纳入当前主题库。"
    return {
        "taxonomy_theme_count": len(taxonomy_names),
        "watchlist_missing_in_taxonomy": missing_watchlist,
        "fund_profile_missing_in_taxonomy": missing_funds,
        "unused_taxonomy_themes": unused,
        "consistency_label": label,
        "consistency_reason": reason,
    }
