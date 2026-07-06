from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

VALID_MEMBER_ROLES = {"core", "related"}
VALID_MAPPING_METHODS = {"manual_domain_mapping", "config_migration", "source_derived", "unknown"}
DEFAULT_MAPPING_SOURCE = "project_defined_theme_taxonomy"
DEFAULT_MAPPING_METHOD = "manual_domain_mapping"


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


def normalize_taxonomy_name(value: object) -> str:
    return "" if value is None else str(value).strip().replace(" ", "").upper()


def _normalize_member_definition(
    value: object,
    theme_name: str,
    role: str,
    strict_representative: bool = False,
    inherited_rationale: str | None = None,
) -> dict:
    if isinstance(value, dict):
        canonical_name = str(value.get("canonical_name") or value.get("member_name") or value.get("sector_name") or value.get("name") or "").strip()
        role_value = str(value.get("role") or role or "").strip()
        aliases = _as_list(value.get("aliases"))
        mapping_source = str(value.get("mapping_source") or DEFAULT_MAPPING_SOURCE).strip()
        mapping_method = str(value.get("mapping_method") or DEFAULT_MAPPING_METHOD).strip()
        rationale = str(value.get("rationale") or inherited_rationale or "").strip()
        enabled = bool(value.get("enabled", True))
        strict = bool(value.get("strict_representative", strict_representative))
        source_reference = str(value.get("source_reference") or "").strip()
    else:
        canonical_name = str(value or "").strip()
        role_value = str(role or "").strip()
        aliases = []
        mapping_source = DEFAULT_MAPPING_SOURCE
        mapping_method = DEFAULT_MAPPING_METHOD
        rationale = str(inherited_rationale or "Inherited from legacy primary/related sector list in project taxonomy config.").strip()
        enabled = True
        strict = bool(strict_representative)
        source_reference = ""
    return {
        "theme_name": theme_name,
        "canonical_name": canonical_name,
        "normalized_canonical_name": normalize_taxonomy_name(canonical_name),
        "role": role_value,
        "aliases": aliases,
        "normalized_aliases": [normalize_taxonomy_name(alias) for alias in aliases],
        "strict_representative": strict,
        "mapping_source": mapping_source,
        "mapping_method": mapping_method,
        "rationale": rationale,
        "source_reference": source_reference,
        "enabled": enabled,
    }


def get_theme_member_definitions(taxonomy: dict, theme_name: str | None = None) -> list[dict]:
    members: list[dict] = []
    target = str(theme_name or "").strip()
    for theme in get_taxonomy_themes(taxonomy):
        name = str(theme.get("theme_name", "")).strip()
        if target and name != target:
            continue
        inherited_rationale = str(theme.get("description") or "").strip()
        explicit_members = theme.get("members")
        if isinstance(explicit_members, list) and explicit_members:
            for item in explicit_members:
                role = str(item.get("role") if isinstance(item, dict) else "").strip() or "related"
                members.append(_normalize_member_definition(item, name, role, inherited_rationale=inherited_rationale))
            continue
        for sector in _as_list(theme.get("primary_sectors")):
            members.append(
                _normalize_member_definition(
                    sector,
                    name,
                    role="core",
                    strict_representative=True,
                    inherited_rationale=inherited_rationale,
                )
            )
        for sector in _as_list(theme.get("related_sectors")):
            members.append(
                _normalize_member_definition(
                    sector,
                    name,
                    role="related",
                    strict_representative=False,
                    inherited_rationale=inherited_rationale,
                )
            )
    return members


def build_theme_member_table(taxonomy: dict) -> pd.DataFrame:
    columns = [
        "theme_name",
        "canonical_name",
        "normalized_canonical_name",
        "role",
        "strict_representative",
        "aliases",
        "mapping_source",
        "mapping_method",
        "rationale",
        "enabled",
    ]
    rows = get_theme_member_definitions(taxonomy)
    if not rows:
        return pd.DataFrame(columns=columns)
    out = pd.DataFrame(rows)
    out["aliases"] = out["aliases"].map(lambda value: "，".join(value or []))
    return out[columns]


def _normalized_config_payload(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _normalized_config_payload(value[key])
            for key in sorted(value)
            if not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [_normalized_config_payload(item) for item in value]
    if isinstance(value, str):
        return value.strip()
    return value


def _fingerprint_payload(value: object) -> str:
    normalized = _normalized_config_payload(value)
    text = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_taxonomy_fingerprint(taxonomy: dict) -> str:
    content = {
        "taxonomy_name": (taxonomy or {}).get("taxonomy_name"),
        "version": (taxonomy or {}).get("version"),
        "themes": get_taxonomy_themes(taxonomy or {}),
    }
    return _fingerprint_payload(content)


def get_theme_definition(taxonomy: dict, theme_name: str) -> dict:
    target = str(theme_name or "").strip()
    for theme in get_taxonomy_themes(taxonomy):
        if str(theme.get("theme_name", "")).strip() == target:
            return copy.deepcopy(theme)
    return {}


def build_theme_definition_fingerprint(theme_definition: dict) -> str:
    member_definitions = get_theme_member_definitions({"themes": [theme_definition]}) if theme_definition else []
    relevant = {
        "theme_name": theme_definition.get("theme_name"),
        "theme_group": theme_definition.get("theme_group"),
        "description": theme_definition.get("description"),
        "members": [
            {
                "canonical_name": item.get("canonical_name"),
                "role": item.get("role"),
                "aliases": item.get("aliases"),
                "strict_representative": item.get("strict_representative"),
                "mapping_source": item.get("mapping_source"),
                "mapping_method": item.get("mapping_method"),
                "rationale": item.get("rationale"),
            }
            for item in member_definitions
            if item.get("enabled", True)
        ],
        "concept_keywords": _as_list(theme_definition.get("concept_keywords")),
        "aliases": _as_list(theme_definition.get("aliases")),
        "overlap_notes": theme_definition.get("overlap_notes"),
    }
    return _fingerprint_payload(relevant)


def build_theme_definition_evidence(
    taxonomy: dict,
    theme_name: str,
    taxonomy_source: str = "config/theme_taxonomy.json",
) -> dict:
    theme_definition = get_theme_definition(taxonomy, theme_name)
    member_definitions = get_theme_member_definitions({"themes": [theme_definition]}) if theme_definition else []
    core_members = [item["canonical_name"] for item in member_definitions if item.get("enabled", True) and item.get("role") == "core"]
    related_members = [item["canonical_name"] for item in member_definitions if item.get("enabled", True) and item.get("role") == "related"]
    strict_representatives = [item["canonical_name"] for item in member_definitions if item.get("enabled", True) and item.get("strict_representative")]
    provenance_counts = dict(Counter(str(item.get("mapping_method") or "unknown") for item in member_definitions if item.get("enabled", True)))
    taxonomy_fingerprint = build_taxonomy_fingerprint(taxonomy or {})
    definition_fingerprint = (
        build_theme_definition_fingerprint(theme_definition)
        if theme_definition
        else _fingerprint_payload({"theme_name": str(theme_name or "").strip(), "missing": True})
    )
    return {
        "theme_id": str(theme_definition.get("theme_name") or theme_name or "").strip(),
        "theme_name": str(theme_definition.get("theme_name") or theme_name or "").strip(),
        "theme_group": str(theme_definition.get("theme_group") or "").strip(),
        "taxonomy_source": taxonomy_source,
        "taxonomy_name": (taxonomy or {}).get("taxonomy_name"),
        "taxonomy_version": (taxonomy or {}).get("version"),
        "taxonomy_fingerprint": taxonomy_fingerprint,
        "theme_definition_fingerprint": definition_fingerprint,
        "core_members": core_members,
        "related_members": related_members,
        "strict_representatives": strict_representatives,
        "member_definitions": member_definitions,
        "member_provenance_counts": provenance_counts,
        "aliases": _as_list(theme_definition.get("aliases")),
        "concept_keywords": _as_list(theme_definition.get("concept_keywords")),
        "calculation_modes": ["strict_representative", "representative", "breadth"],
        "description": str(theme_definition.get("description") or "").strip(),
        "overlap_notes": str(theme_definition.get("overlap_notes") or "").strip(),
        "definition_found": bool(theme_definition),
    }


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


def build_alias_resolution_index(taxonomy: dict) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = defaultdict(list)
    for member in get_theme_member_definitions(taxonomy):
        if not member.get("enabled", True):
            continue
        canonical = member.get("canonical_name", "")
        entries = [(canonical, "canonical_exact")] + [(alias, "explicit_alias") for alias in member.get("aliases", [])]
        for label, matched_by in entries:
            normalized = normalize_taxonomy_name(label)
            if not normalized:
                continue
            index[normalized].append(
                {
                    "theme_name": member.get("theme_name"),
                    "canonical_member": canonical,
                    "matched_by": matched_by,
                    "alias_used": "" if matched_by == "canonical_exact" else label,
                    "role": member.get("role"),
                    "strict_representative": bool(member.get("strict_representative")),
                    "mapping_source": member.get("mapping_source"),
                    "mapping_method": member.get("mapping_method"),
                    "mapping_rationale": member.get("rationale"),
                }
            )
    return index


def resolve_theme_member_alias(source_name: str, taxonomy: dict) -> dict:
    normalized = normalize_taxonomy_name(source_name)
    candidates = build_alias_resolution_index(taxonomy).get(normalized, [])
    candidate_members = sorted({str(item.get("canonical_member") or "") for item in candidates if item.get("canonical_member")})
    candidate_themes = sorted({str(item.get("theme_name") or "") for item in candidates if item.get("theme_name")})
    if not candidates:
        return {
            "source_name": str(source_name or ""),
            "normalized_source_name": normalized,
            "canonical_member": None,
            "matched_by": "unmatched",
            "alias_used": None,
            "ambiguity_status": "unmatched",
            "candidate_members": [],
            "candidate_themes": [],
            "candidates": [],
        }
    if len(candidate_members) > 1 or len(candidate_themes) > 1:
        return {
            "source_name": str(source_name or ""),
            "normalized_source_name": normalized,
            "canonical_member": None,
            "matched_by": "ambiguous",
            "alias_used": None,
            "ambiguity_status": "ambiguous",
            "candidate_members": candidate_members,
            "candidate_themes": candidate_themes,
            "candidates": candidates,
        }
    candidate = candidates[0]
    return {
        "source_name": str(source_name or ""),
        "normalized_source_name": normalized,
        "canonical_member": candidate.get("canonical_member"),
        "matched_by": candidate.get("matched_by"),
        "alias_used": candidate.get("alias_used") or None,
        "ambiguity_status": "resolved",
        "candidate_members": candidate_members,
        "candidate_themes": candidate_themes,
        "candidates": candidates,
        "role": candidate.get("role"),
        "strict_representative": bool(candidate.get("strict_representative")),
        "mapping_source": candidate.get("mapping_source"),
        "mapping_method": candidate.get("mapping_method"),
        "mapping_rationale": candidate.get("mapping_rationale"),
    }


def validate_theme_taxonomy_structured(taxonomy: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(taxonomy, dict):
        return {"is_valid": False, "errors": ["taxonomy 不是 JSON object。"], "warnings": []}
    themes = get_taxonomy_themes(taxonomy)
    if not themes:
        errors.append("themes 不存在或为空。")
    names = [str(theme.get("theme_name", "")).strip() for theme in themes if str(theme.get("theme_name", "")).strip()]
    for name, count in Counter(names).items():
        if count > 1:
            errors.append(f"重复 theme ID/name: {name}。")
    member_rows = get_theme_member_definitions(taxonomy)
    by_theme: dict[str, list[dict]] = defaultdict(list)
    for member in member_rows:
        by_theme[str(member.get("theme_name") or "")].append(member)
        if not member.get("canonical_name"):
            errors.append(f"{member.get('theme_name') or '<unknown>'}: 存在空 canonical member。")
        if member.get("role") not in VALID_MEMBER_ROLES:
            errors.append(f"{member.get('theme_name')}: {member.get('canonical_name')} role 无效：{member.get('role')}。")
        if member.get("mapping_method") not in VALID_MAPPING_METHODS:
            warnings.append(f"{member.get('theme_name')}: {member.get('canonical_name')} mapping_method 未知：{member.get('mapping_method')}。")
        if not member.get("rationale"):
            warnings.append(f"{member.get('theme_name')}: {member.get('canonical_name')} 缺少 mapping rationale。")
        if not member.get("mapping_source") or member.get("mapping_method") == "unknown":
            warnings.append(f"{member.get('theme_name')}: {member.get('canonical_name')} mapping provenance 不完整。")
    for theme_name, rows in by_theme.items():
        enabled = [item for item in rows if item.get("enabled", True)]
        if not enabled:
            errors.append(f"{theme_name}: 空主题或全部成员 disabled。")
            continue
        names_in_theme = [item.get("normalized_canonical_name") for item in enabled]
        for normalized, count in Counter(names_in_theme).items():
            if normalized and count > 1:
                errors.append(f"{theme_name}: 同一主题内重复成员 {normalized}。")
        strict_members = [item for item in enabled if item.get("strict_representative")]
        if not strict_members:
            warnings.append(f"{theme_name}: 没有 strict representative。")
        for item in strict_members:
            if item.get("role") != "core":
                warnings.append(f"{theme_name}: {item.get('canonical_name')} 是 strict representative 但 role 不是 core。")
    member_to_themes: dict[str, set[str]] = defaultdict(set)
    strict_to_themes: dict[str, set[str]] = defaultdict(set)
    for member in member_rows:
        if not member.get("enabled", True):
            continue
        normalized = member.get("normalized_canonical_name")
        member_to_themes[normalized].add(str(member.get("theme_name")))
        if member.get("strict_representative"):
            strict_to_themes[normalized].add(str(member.get("theme_name")))
    for normalized, theme_names in sorted(member_to_themes.items()):
        if normalized and len(theme_names) > 1:
            warnings.append(f"{normalized}: 成员出现在多个主题：{', '.join(sorted(theme_names))}。")
    for normalized, theme_names in sorted(strict_to_themes.items()):
        if normalized and len(theme_names) > 1:
            warnings.append(f"{normalized}: strict representative 出现在多个主题：{', '.join(sorted(theme_names))}。")
    alias_index = build_alias_resolution_index(taxonomy)
    alias_collisions = {}
    for alias, candidates in alias_index.items():
        members = {item.get("canonical_member") for item in candidates}
        themes_for_alias = {item.get("theme_name") for item in candidates}
        matched_by_values = {item.get("matched_by") for item in candidates}
        is_reused_canonical = matched_by_values == {"canonical_exact"} and len(members) == 1 and len(themes_for_alias) > 1
        if is_reused_canonical:
            warnings.append(f"{alias}: canonical member 被多个主题复用，解析源行时会标记为 ambiguous。")
        elif len(members) > 1 or len(themes_for_alias) > 1:
            alias_collisions[alias] = candidates
            errors.append(f"{alias}: alias/canonical 解析到多个候选，必须显式处理歧义。")
    load_warning = taxonomy.get("_load_warning")
    if load_warning:
        warnings.insert(0, str(load_warning))
    return {
        "is_valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "alias_collisions": alias_collisions,
        "member_count": len(member_rows),
        "unique_member_count": len({item.get("normalized_canonical_name") for item in member_rows if item.get("normalized_canonical_name")}),
    }


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
    group_by_theme = {str(theme.get("theme_name", "")).strip(): str(theme.get("theme_group", "")).strip() for theme in get_taxonomy_themes(taxonomy)}
    for member in get_theme_member_definitions(taxonomy):
        role = member.get("role")
        rows.append(
            {
                "sector_name": member.get("canonical_name"),
                "theme_name": member.get("theme_name"),
                "sector_role": "primary" if role == "core" else "related",
                "member_role": role,
                "strict_representative": bool(member.get("strict_representative")),
                "theme_group": group_by_theme.get(str(member.get("theme_name") or ""), ""),
                "mapping_source": member.get("mapping_source"),
                "mapping_method": member.get("mapping_method"),
                "rationale": member.get("rationale"),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "sector_name",
            "theme_name",
            "sector_role",
            "member_role",
            "strict_representative",
            "theme_group",
            "mapping_source",
            "mapping_method",
            "rationale",
        ],
    )


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
        members = [item for item in get_theme_member_definitions({"themes": [theme]}) if item.get("enabled", True)]
        definitions[name] = {
            "primary_sectors": [item["canonical_name"] for item in members if item.get("role") == "core"],
            "related_sectors": [item["canonical_name"] for item in members if item.get("role") == "related"],
            "member_definitions": members,
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
