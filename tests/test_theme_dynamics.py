from __future__ import annotations

import pandas as pd

from src.theme_dynamics import (
    DAILY_SELECTION_POLICY,
    build_cross_date_state_evolution,
    build_member_structural_divergence,
    build_scope_divergence_table,
    build_state_transition_trace,
    build_theme_dynamics_evidence,
    build_theme_observation_cube,
    get_theme_observation_grain,
    render_theme_dynamics_brief_section,
    select_daily_observations,
    validate_theme_dynamics_text,
)


def _write_snapshot(path, trade_date: str, rows: list[dict]) -> None:
    frame = pd.DataFrame(rows)
    frame["trade_date"] = trade_date
    frame["sector_type"] = "行业资金流"
    frame["source"] = frame.get("source", "SAMPLE")
    frame["data_mode"] = frame.get("data_mode", "SAMPLE")
    frame.to_csv(path / f"sector_flow_{trade_date}.csv", index=False)


def _sample_rows(time_value: str, semi: float, electronic: float = 0.0) -> list[dict]:
    return [
        {"captured_time": time_value, "sector_name": "半导体", "main_net_inflow_billion": semi},
        {"captured_time": time_value, "sector_name": "电子", "main_net_inflow_billion": electronic},
        {"captured_time": time_value, "sector_name": "计算机", "main_net_inflow_billion": -10.0},
    ]


def test_observation_grain_is_explicit() -> None:
    assert get_theme_observation_grain() == (
        "theme_name",
        "trade_date",
        "captured_time_bucket",
        "calculation_mode",
        "source_mode",
        "taxonomy_fingerprint",
        "theme_definition_fingerprint",
    )


def test_build_theme_observation_cube_from_sample_data() -> None:
    cube = build_theme_observation_cube(source_mode="SAMPLE", calculation_modes=["strict_representative"])
    assert not cube.empty
    row = cube[cube["theme_name"].eq("半导体/芯片链")].iloc[0]
    assert row["source_mode"] == "SAMPLE"
    assert row["calculation_mode"] == "strict_representative"
    assert row["taxonomy_fingerprint"]
    assert row["theme_definition_fingerprint"]
    assert row["observation_id"]
    assert row["derived_state"]


def test_cube_supports_multiple_modes_and_ordering() -> None:
    cube = build_theme_observation_cube(source_mode="SAMPLE", calculation_modes=["breadth", "strict_representative"])
    modes = cube["calculation_mode"].dropna().unique().tolist()
    assert set(modes) == {"breadth", "strict_representative"}
    sorted_copy = cube.sort_values(["source_mode", "theme_name", "trade_date", "captured_time_bucket", "calculation_mode"]).reset_index(drop=True)
    assert cube["observation_id"].tolist() == sorted_copy["observation_id"].tolist()


def test_cube_uses_temp_real_cache_without_sample_mixing(tmp_path) -> None:
    _write_snapshot(tmp_path, "2026-01-01", _sample_rows("09:30:00", 40.0))
    cube = build_theme_observation_cube(source_mode="REAL", data_dir=str(tmp_path), calculation_modes=["strict_representative"])
    assert not cube.empty
    assert set(cube["source_mode"]) == {"REAL"}


def test_duplicate_grain_detection(tmp_path) -> None:
    rows = _sample_rows("09:30:00", 40.0) + _sample_rows("09:30:30", 45.0)
    _write_snapshot(tmp_path, "2026-01-01", rows)
    cube = build_theme_observation_cube(source_mode="SAMPLE", data_dir=str(tmp_path), calculation_modes=["strict_representative"])
    # Both captured_time values normalize to the same 09:30 bucket.
    assert cube.attrs["duplicate_grain_count"] > 0
    assert cube["duplicate_grain"].any()


def test_state_transition_trace_empty_and_single() -> None:
    empty = build_state_transition_trace(pd.DataFrame())
    assert empty["trace_available"] is False
    one = build_state_transition_trace(pd.DataFrame([{"trade_date": "2026-01-01", "captured_time_bucket": "09:30", "derived_state": "强流入"}]))
    assert one["observation_count"] == 1
    assert one["transition_count"] == 0
    assert one["longest_positive_streak"] == 1


def test_state_transition_trace_counts_and_streaks() -> None:
    df = pd.DataFrame(
        [
            {"trade_date": "2026-01-01", "captured_time_bucket": "09:30", "derived_state": "强流入"},
            {"trade_date": "2026-01-01", "captured_time_bucket": "10:30", "derived_state": "弱流入"},
            {"trade_date": "2026-01-02", "captured_time_bucket": "09:30", "derived_state": "分歧/中性"},
            {"trade_date": "2026-01-02", "captured_time_bucket": "10:30", "derived_state": "强流出"},
            {"trade_date": "2026-01-03", "captured_time_bucket": "09:30", "derived_state": "强流出"},
        ]
    )
    trace = build_state_transition_trace(df)
    assert trace["transition_count"] == 3
    assert trace["positive_state_count"] == 2
    assert trace["neutral_state_count"] == 1
    assert trace["negative_state_count"] == 2
    assert trace["positive_state_share"] == 0.4
    assert trace["longest_negative_streak"] == 2
    assert trace["latest_transition"] == ("分歧/中性", "强流出")


def test_cross_date_evolution_uses_latest_per_date_policy() -> None:
    df = pd.DataFrame(
        [
            {"trade_date": "2026-01-01", "captured_time_bucket": "09:30", "derived_state": "强流出", "taxonomy_fingerprint": "a", "schema_fingerprint": "s"},
            {"trade_date": "2026-01-01", "captured_time_bucket": "14:50", "derived_state": "强流入", "taxonomy_fingerprint": "a", "schema_fingerprint": "s"},
            {"trade_date": "2026-01-02", "captured_time_bucket": "14:50", "derived_state": "弱流入", "taxonomy_fingerprint": "a", "schema_fingerprint": "s"},
        ]
    )
    selected = select_daily_observations(df)
    assert selected["derived_state"].tolist() == ["强流入", "弱流入"]
    evolution = build_cross_date_state_evolution(df)
    assert evolution["daily_selection_policy"] == DAILY_SELECTION_POLICY
    assert evolution["daily_state_path"] == ["强流入", "弱流入"]


def _scope_cube(states: dict[str, str]) -> pd.DataFrame:
    rows = []
    for mode, state in states.items():
        rows.append(
            {
                "theme_name": "T",
                "trade_date": "2026-01-01",
                "captured_time_bucket": "09:30",
                "source_mode": "SAMPLE",
                "taxonomy_fingerprint": "tax",
                "theme_definition_fingerprint": "def",
                "calculation_mode": mode,
                "derived_state": state,
                "aggregate_value": 1.0,
            }
        )
    return pd.DataFrame(rows)


def test_scope_divergence_aligned_positive() -> None:
    table = build_scope_divergence_table(
        _scope_cube({"strict_representative": "强流入", "representative": "强流入", "breadth": "强流入"})
    )
    assert table.iloc[0]["scope_divergence_state"] == "aligned_positive"
    assert bool(table.iloc[0]["all_scopes_equal"]) is True


def test_scope_divergence_representative_positive_breadth_negative() -> None:
    table = build_scope_divergence_table(
        _scope_cube({"representative": "弱流入", "breadth": "强流出"})
    )
    assert table.iloc[0]["scope_divergence_state"] == "representative_positive_breadth_negative"


def test_scope_divergence_insufficient_scopes() -> None:
    table = build_scope_divergence_table(_scope_cube({"strict_representative": "强流入"}))
    assert table.iloc[0]["scope_divergence_state"] == "insufficient_scopes"


def test_member_divergence_states() -> None:
    aligned = build_member_structural_divergence(
        [{"included": True, "input_value": 10.0}, {"included": True, "input_value": 2.0}]
    )
    assert aligned["member_sign_agreement"] == "aligned_positive"
    mixed = build_member_structural_divergence(
        [{"included": True, "input_value": 10.0}, {"included": True, "input_value": -9.0}]
    )
    assert mixed["member_sign_agreement"] == "balanced_divergence"
    single = build_member_structural_divergence([{"included": True, "input_value": 0.0}])
    assert single["member_sign_agreement"] == "insufficient_members"


def test_theme_dynamics_evidence_sample_label_and_lineage() -> None:
    cube = build_theme_observation_cube(source_mode="SAMPLE")
    evidence = build_theme_dynamics_evidence(cube, "半导体/芯片链", source_mode="SAMPLE")
    assert evidence["dynamics_available"] is True
    assert evidence["source_mode"] == "SAMPLE"
    assert any("SAMPLE" in item for item in evidence["warnings"])
    assert evidence["lineage_compatible"] is True


def test_theme_dynamics_rejects_mixed_theme_definition() -> None:
    cube = build_theme_observation_cube(source_mode="SAMPLE", calculation_modes=["strict_representative"])
    mask = cube["theme_name"].eq("半导体/芯片链")
    idx = cube[mask].index[:1]
    cube.loc[idx, "theme_definition_fingerprint"] = "different"
    evidence = build_theme_dynamics_evidence(cube, "半导体/芯片链", source_mode="SAMPLE")
    assert evidence["lineage_compatible"] is False
    assert evidence["dynamics_available"] is False


def test_render_theme_dynamics_brief_section_safe_wording() -> None:
    cube = build_theme_observation_cube(source_mode="SAMPLE")
    evidence = build_theme_dynamics_evidence(cube, "半导体/芯片链", source_mode="SAMPLE")
    section = render_theme_dynamics_brief_section(evidence)
    assert "主题动态证据" in section
    assert "SAMPLE" in section
    assert validate_theme_dynamics_text(section) == []


def test_validate_theme_dynamics_text_catches_forbidden() -> None:
    hits = validate_theme_dynamics_text("这里写了胜率和未来会涨")
    assert "胜率" in hits
    assert "未来会涨" in hits
