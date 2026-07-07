from __future__ import annotations

from tools.inspect_theme_relationships import main


def test_relationship_cli_json_output(capsys):
    assert main(["--source-mode", "SAMPLE", "--mode", "strict_representative", "--json", "--limit", "2"]) == 0
    out = capsys.readouterr().out
    assert "relationship_observation_basis" in out
    assert "topology_summary" in out


def test_relationship_cli_pair_output(capsys):
    assert main(["--source-mode", "SAMPLE", "--mode", "strict_representative", "--pair", "AI算力/TMT::半导体/芯片链"]) == 0
    out = capsys.readouterr().out
    assert "Cross-theme relationship evidence" in out
    assert "aligned canonical observations" in out


def test_relationship_cli_co_transition_output(capsys):
    assert main(["--source-mode", "SAMPLE", "--mode", "strict_representative", "--pair", "AI算力/TMT::半导体/芯片链", "--co-transitions"]) == 0
    out = capsys.readouterr().out
    assert "Observed co-transition evidence" in out


def test_relationship_cli_top_semantic_overlap(capsys):
    assert main(["--source-mode", "SAMPLE", "--top-semantic-overlap", "--limit", "3"]) == 0
    out = capsys.readouterr().out
    assert "taxonomy Jaccard" in out or "Taxonomy" in out


def test_relationship_cli_invalid_pair_syntax(capsys):
    assert main(["--source-mode", "SAMPLE", "--pair", "AI算力/TMT"]) == 2
    err = capsys.readouterr().err
    assert "Invalid pair syntax" in err


def test_relationship_cli_missing_real_cache_safe(tmp_path, capsys):
    status = main(["--source-mode", "REAL", "--data-dir", str(tmp_path), "--json"])
    out = capsys.readouterr().out
    assert status == 0
    assert "alignment_summary" in out

