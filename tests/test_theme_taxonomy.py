from __future__ import annotations

import json
from pathlib import Path

from src.theme_taxonomy import (
    audit_theme_name_consistency,
    build_taxonomy_fingerprint,
    build_theme_definition_evidence,
    build_theme_definition_fingerprint,
    build_concept_keyword_table,
    build_sector_to_theme_map,
    build_theme_definition_table,
    build_theme_member_table,
    get_theme_member_definitions,
    get_theme_names,
    load_theme_taxonomy,
    resolve_theme_member_alias,
    validate_theme_taxonomy_structured,
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
    member_table = build_theme_member_table(taxonomy)
    assert {"canonical_name", "role", "strict_representative", "mapping_method"}.issubset(member_table.columns)


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


def test_taxonomy_fingerprint_is_key_order_stable() -> None:
    taxonomy_a = {
        "version": "v-test",
        "taxonomy_name": "测试主题库",
        "themes": [
            {
                "theme_name": "A",
                "primary_sectors": ["A1"],
                "related_sectors": ["A2"],
                "concept_keywords": [],
            }
        ],
    }
    taxonomy_b = {
        "themes": [
            {
                "related_sectors": ["A2"],
                "concept_keywords": [],
                "primary_sectors": ["A1"],
                "theme_name": "A",
            }
        ],
        "taxonomy_name": "测试主题库",
        "version": "v-test",
    }
    assert build_taxonomy_fingerprint(taxonomy_a) == build_taxonomy_fingerprint(taxonomy_b)


def test_theme_definition_fingerprint_changes_with_definition() -> None:
    base = {
        "theme_name": "A",
        "primary_sectors": ["A1"],
        "related_sectors": ["A2"],
        "concept_keywords": [],
    }
    changed = {**base, "related_sectors": ["A2", "A3"]}
    assert build_theme_definition_fingerprint(base) != build_theme_definition_fingerprint(changed)


def test_theme_definition_evidence_is_scoped_to_selected_theme() -> None:
    taxonomy = {
        "taxonomy_name": "测试主题库",
        "version": "v-test",
        "themes": [
            {"theme_name": "A", "primary_sectors": ["A1"], "related_sectors": ["A2"], "concept_keywords": []},
            {"theme_name": "B", "primary_sectors": ["B1"], "related_sectors": ["B2"], "concept_keywords": []},
        ],
    }
    changed_other = {
        **taxonomy,
        "themes": [
            {"theme_name": "A", "primary_sectors": ["A1"], "related_sectors": ["A2"], "concept_keywords": []},
            {"theme_name": "B", "primary_sectors": ["B9"], "related_sectors": ["B2"], "concept_keywords": []},
        ],
    }
    assert (
        build_theme_definition_evidence(taxonomy, "A")["theme_definition_fingerprint"]
        == build_theme_definition_evidence(changed_other, "A")["theme_definition_fingerprint"]
    )
    assert build_theme_definition_evidence(taxonomy, "A")["taxonomy_fingerprint"] != build_theme_definition_evidence(changed_other, "A")["taxonomy_fingerprint"]


def test_legacy_taxonomy_members_get_explicit_roles() -> None:
    taxonomy = {"themes": [{"theme_name": "A", "primary_sectors": ["A1"], "related_sectors": ["A2"], "concept_keywords": []}]}
    members = get_theme_member_definitions(taxonomy)
    by_name = {item["canonical_name"]: item for item in members}
    assert by_name["A1"]["role"] == "core"
    assert by_name["A1"]["strict_representative"] is True
    assert by_name["A2"]["role"] == "related"
    assert by_name["A2"]["mapping_method"] == "manual_domain_mapping"


def test_explicit_member_shape_loads_and_resolves_alias() -> None:
    taxonomy = {
        "themes": [
            {
                "theme_name": "A",
                "members": [
                    {
                        "canonical_name": "半导体",
                        "role": "core",
                        "aliases": ["芯片"],
                        "strict_representative": True,
                        "mapping_method": "manual_domain_mapping",
                        "rationale": "项目配置中的显式测试映射。",
                    }
                ],
            }
        ]
    }
    result = resolve_theme_member_alias("芯片", taxonomy)
    assert result["matched_by"] == "explicit_alias"
    assert result["canonical_member"] == "半导体"
    assert result["ambiguity_status"] == "resolved"


def test_alias_collision_is_structural_error_and_not_silent() -> None:
    taxonomy = {
        "themes": [
            {"theme_name": "A", "members": [{"canonical_name": "A1", "role": "core", "aliases": ["共同"], "rationale": "x"}]},
            {"theme_name": "B", "members": [{"canonical_name": "B1", "role": "core", "aliases": ["共同"], "rationale": "x"}]},
        ]
    }
    validation = validate_theme_taxonomy_structured(taxonomy)
    assert validation["error_count"] >= 1
    resolved = resolve_theme_member_alias("共同", taxonomy)
    assert resolved["matched_by"] == "ambiguous"
    assert resolved["ambiguity_status"] == "ambiguous"


def test_reused_canonical_member_is_warning_not_error() -> None:
    taxonomy = {
        "themes": [
            {"theme_name": "A", "primary_sectors": ["银行"], "related_sectors": [], "concept_keywords": []},
            {"theme_name": "B", "primary_sectors": [], "related_sectors": ["银行"], "concept_keywords": []},
        ]
    }
    validation = validate_theme_taxonomy_structured(taxonomy)
    assert validation["error_count"] == 0
    assert validation["warning_count"] >= 1
    resolved = resolve_theme_member_alias("银行", taxonomy)
    assert resolved["ambiguity_status"] == "ambiguous"


def test_structured_validator_detects_invalid_role_and_duplicate_member() -> None:
    taxonomy = {
        "themes": [
            {
                "theme_name": "A",
                "members": [
                    {"canonical_name": "A1", "role": "core", "rationale": "x"},
                    {"canonical_name": "A1", "role": "bad", "rationale": "x"},
                ],
            }
        ]
    }
    validation = validate_theme_taxonomy_structured(taxonomy)
    assert validation["error_count"] >= 2
