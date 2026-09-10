from __future__ import annotations

import pandas as pd

from src.theme_observation_evidence import (
    build_theme_research_snapshot,
    build_theme_data_evidence,
    build_theme_evidence_contribution_table,
    get_theme_observation_theme_options,
    build_theme_observation_evidence,
    render_brief_provenance_section,
    render_theme_extended_evidence_unavailable_section,
    render_theme_research_snapshot_section,
    resolve_theme_observation_evidence,
    validate_theme_evidence_text,
)
from src.theme_taxonomy import load_theme_taxonomy


def _row(name: str, value: float, source_mode: str = "SAMPLE") -> dict:
    return {
        "trade_date": "2026-01-16",
        "captured_at": "2026-01-16 14:50:00",
        "captured_time": "14:50:00",
        "sector_type": "行业资金流",
        "sector_name": name,
        "main_net_inflow_billion": value,
        "source": source_mode,
        "data_mode": source_mode,
    }


def _write_snapshot(path, date: str, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path / f"sector_flow_{date}.csv", index=False)


def test_build_theme_observation_evidence_sample_warning_and_trace() -> None:
    latest = pd.DataFrame([_row("半导体", 35.0), _row("半导体设备", -5.0)])
    evidence = build_theme_observation_evidence(
        latest,
        "半导体/芯片链",
        theme_mode="strict_representative",
        taxonomy=load_theme_taxonomy(),
        source_mode="SAMPLE",
        manifest_df=pd.DataFrame(),
    )
    assert evidence["evidence_available"] is True
    assert evidence["source_mode"] == "SAMPLE"
    assert evidence["aggregate_value"] == 35.0
    assert evidence["derived_state"] == "强流入"
    assert any("SAMPLE" in item for item in evidence["warnings"])
    table = build_theme_evidence_contribution_table(evidence)
    assert "半导体" in table["member_name"].tolist()
    assert bool(table[table["member_name"].eq("半导体")]["included"].iloc[0]) is True
    included = table[table["member_name"].eq("半导体")].iloc[0]
    assert included["canonical_member"] == "半导体"
    assert included["matched_by"] == "canonical_exact"
    assert included["mapping_method"] == "manual_domain_mapping"


def test_theme_observation_evidence_observation_id_is_deterministic() -> None:
    latest = pd.DataFrame([_row("半导体", 35.0)])
    kwargs = {
        "theme_name": "半导体/芯片链",
        "theme_mode": "strict_representative",
        "taxonomy": load_theme_taxonomy(),
        "source_mode": "REAL",
        "manifest_df": pd.DataFrame(),
    }
    first = build_theme_observation_evidence(latest, **kwargs)
    second = build_theme_observation_evidence(latest, **kwargs)
    assert first["observation_id"] == second["observation_id"]
    assert not any("SAMPLE" in item for item in first["warnings"])


def test_build_theme_research_snapshot_summarizes_existing_sample_evidence() -> None:
    evidence = build_theme_observation_evidence(
        pd.DataFrame([_row("半导体", 35.0), _row("半导体设备", -5.0)]),
        "半导体/芯片链",
        taxonomy=load_theme_taxonomy(),
        source_mode="SAMPLE",
        manifest_df=pd.DataFrame(),
    )

    snapshot = build_theme_research_snapshot(evidence)

    assert snapshot["research_snapshot_available"] is True
    assert snapshot["observed_state"] == "强流入"
    assert snapshot["aggregate_value"] == 35.0
    assert "匹配" in snapshot["member_coverage_label"]
    assert "SAMPLE 合成演示数据" in snapshot["source_notice"]
    assert validate_theme_evidence_text("\n".join(snapshot["limitations"] + [snapshot["source_notice"]])) == []


def test_build_theme_research_snapshot_handles_unavailable_evidence() -> None:
    snapshot = build_theme_research_snapshot(
        {"theme_name": "不存在主题", "source_mode": "REAL", "warnings": ["当前没有可用快照。"]}
    )

    assert snapshot["research_snapshot_available"] is False
    assert snapshot["observed_state"] == "暂无主题观察"
    assert snapshot["limitations"] == ["当前没有可用快照。"]


def test_get_theme_observation_theme_options_preserves_preferred_order() -> None:
    preferred = pd.DataFrame({"theme_name": ["半导体/芯片链", "", "AI算力/TMT"]})
    fallback = pd.DataFrame({"theme_name": ["AI算力/TMT", "新能源链", None]})

    assert get_theme_observation_theme_options(preferred, fallback) == ["半导体/芯片链", "AI算力/TMT", "新能源链"]


def test_build_theme_data_evidence_dimensions_and_schema_warning() -> None:
    manifest = pd.DataFrame(
        [
            {
                "is_readable": True,
                "is_empty": False,
                "trade_date": "2026-01-15",
                "captured_times": ["09:30:00"],
                "captured_time_buckets": ["09:30"],
                "schema_fingerprint": "a",
                "contract_ok": True,
            },
            {
                "is_readable": True,
                "is_empty": False,
                "trade_date": "2026-01-16",
                "captured_times": ["09:30:00", "10:00:00", "11:00:00", "13:00:00"],
                "captured_time_buckets": ["09:30", "10:00", "11:00", "13:00"],
                "schema_fingerprint": "b",
                "contract_ok": True,
            },
        ]
    )
    evidence = build_theme_data_evidence(manifest, selected_trade_date="2026-01-16", source_mode="REAL")
    assert evidence["history_span_state"] == "multi_date"
    assert evidence["coverage_consistency_state"] == "uneven"
    assert evidence["schema_consistent"] is False


def test_resolve_theme_observation_evidence_unknown_theme() -> None:
    evidence = resolve_theme_observation_evidence("不存在主题", source_mode="SAMPLE")
    assert evidence["evidence_available"] is False
    assert "未知主题" in evidence["warnings"][0]


def test_resolve_theme_observation_evidence_real_data_dir(tmp_path) -> None:
    _write_snapshot(tmp_path, "2026-01-16", [_row("半导体", 35.0, source_mode="REAL")])
    evidence = resolve_theme_observation_evidence(
        "半导体/芯片链",
        source_mode="REAL",
        data_dir=str(tmp_path),
    )
    assert evidence["evidence_available"] is True
    assert evidence["source_mode"] == "REAL"
    assert evidence["as_of_trade_date"] == "2026-01-16"
    assert evidence["aggregate_value"] == 35.0


def test_render_brief_provenance_section_is_compliant() -> None:
    latest = pd.DataFrame([_row("半导体", 35.0)])
    evidence = build_theme_observation_evidence(
        latest,
        "半导体/芯片链",
        taxonomy=load_theme_taxonomy(),
        source_mode="SAMPLE",
        manifest_df=pd.DataFrame(),
    )
    section = render_brief_provenance_section(evidence)
    assert "简报证据口径" in section
    assert "SAMPLE" in section
    assert validate_theme_evidence_text(section) == []


def test_render_theme_research_snapshot_section_is_compliant_and_readable() -> None:
    evidence = build_theme_observation_evidence(
        pd.DataFrame([_row("半导体", 35.0), _row("半导体设备", -5.0)]),
        "半导体/芯片链",
        taxonomy=load_theme_taxonomy(),
        source_mode="SAMPLE",
        manifest_df=pd.DataFrame(),
    )

    section = render_theme_research_snapshot_section(evidence)

    assert "主题观察结论" in section
    assert "当前状态：强流入" in section
    assert "匹配" in section
    assert "SAMPLE 合成演示数据" in section
    assert "快照覆盖" in section
    assert "不等同于 contract-qualified 多日历史" in section
    assert "不预测未来走势" in section
    assert validate_theme_evidence_text(section) == []


def test_render_theme_extended_evidence_unavailable_section_is_compliant() -> None:
    section = render_theme_extended_evidence_unavailable_section("半导体/芯片链")

    assert "扩展主题证据状态" in section
    assert "半导体/芯片链" in section
    assert "未能生成" in section
    assert "不预测未来走势" in section
    assert validate_theme_evidence_text(section) == []
