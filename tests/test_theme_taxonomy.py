from __future__ import annotations

import json
from pathlib import Path

from src.theme_taxonomy import (
    audit_theme_name_consistency,
    build_concept_keyword_table,
    build_sector_to_theme_map,
    build_theme_definition_table,
    get_theme_names,
    load_theme_taxonomy,
    validate_theme_taxonomy,
)


FORBIDDEN = ["买入", "卖出", "加仓", "减仓", "抄底", "逃顶", "推荐买", "建议买", "建仓", "清仓"]


def test_load_theme_taxonomy_missing_returns_default(tmp_path: Path) -> None:
    taxonomy = load_theme_taxonomy(str(tmp_path / "missing.json"))
    assert taxonomy["taxonomy_name"] == "养基宝基金主题观察池"
    assert get_theme_names(taxonomy)
    assert "_load_warning" in taxonomy


def test_validate_theme_taxonomy_detects_duplicate_theme_name() -> None:
    taxonomy = {
        "taxonomy_name": "x",
        "themes": [
            {"theme_name": "A", "primary_sectors": [], "related_sectors": [], "concept_keywords": []},
            {"theme_name": "A", "primary_sectors": [], "related_sectors": [], "concept_keywords": []},
        ],
    }
    warnings = validate_theme_taxonomy(taxonomy)
    assert any("重复 theme_name" in warning for warning in warnings)


def test_get_theme_names_and_tables_have_expected_columns() -> None:
    taxonomy = load_theme_taxonomy()
    assert "半导体/芯片链" in get_theme_names(taxonomy)
    definition = build_theme_definition_table(taxonomy)
    assert {"theme_name", "theme_group", "primary_sectors", "related_sectors", "concept_keywords"}.issubset(definition.columns)
    sector_map = build_sector_to_theme_map(taxonomy)
    assert {"sector_name", "theme_name", "sector_role", "theme_group"}.issubset(sector_map.columns)
    assert {"primary", "related"}.issubset(set(sector_map["sector_role"]))
    keywords = build_concept_keyword_table(taxonomy)
    assert {"theme_name", "concept_keyword", "theme_group"}.issubset(keywords.columns)


def test_audit_theme_name_consistency_detects_unregistered_themes() -> None:
    taxonomy = load_theme_taxonomy()
    result = audit_theme_name_consistency(taxonomy, ["半导体/芯片链", "未注册主题"], ["新能源链"])
    assert result["consistency_label"] == "存在未注册主题"
    assert result["watchlist_missing_in_taxonomy"] == ["未注册主题"]


def test_taxonomy_json_and_text_has_no_advice_words() -> None:
    taxonomy = load_theme_taxonomy()
    text = json.dumps(taxonomy, ensure_ascii=False)
    for word in FORBIDDEN:
        assert word not in text
