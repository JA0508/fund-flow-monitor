import json

from streamlit.testing.v1 import AppTest


def _app(path, enabled=True):
    return AppTest.from_string(
        "from pathlib import Path\n"
        "import streamlit as st\n"
        "from src.watchlist_ui import render_personal_watchlist\n"
        f"result = render_personal_watchlist({{'themes': ['A']}}, ['A', 'B'], Path({str(path)!r}), enabled={enabled!r})\n"
        "st.json(result)\n"
    ).run()


def test_save_and_restore_in_new_session(tmp_path):
    path = tmp_path / "watchlist.json"
    app = _app(path)
    assert not path.exists()
    app.multiselect[0].set_value(["B"])
    app.button[0].click().run()
    assert not app.exception
    assert app.success
    reopened = _app(path)
    assert reopened.multiselect[0].value == ["B"]
    reopened.multiselect[0].set_value([])
    reopened.button[0].click().run()
    assert _app(path).multiselect[0].value == []


def test_disabled_mode_does_not_read_personal_file(tmp_path):
    path = tmp_path / "watchlist.json"
    path.write_bytes(b"not json: private")
    app = _app(path, enabled=False)
    assert not app.exception
    assert not app.multiselect
    assert not app.warning
    assert "private" not in str(app)
    assert path.read_bytes() == b"not json: private"


def test_consecutive_saves_in_same_session(tmp_path):
    path = tmp_path / "watchlist.json"
    app = _app(path)
    app.multiselect[0].set_value(["B"])
    app.button[0].click().run()
    app.multiselect[0].set_value([])
    app.button[0].click().run()
    assert not app.exception
    assert _app(path).multiselect[0].value == []


def test_changed_saved_watchlist_resets_stale_research_selection(tmp_path):
    app = _app(tmp_path / "watchlist.json")
    app.session_state["theme_radar_evidence_theme"] = "A"
    app.session_state["brief_provenance_theme"] = "A"
    app.session_state["brief_provenance_theme_user_selected"] = True
    app.multiselect[0].set_value(["B"])
    app.button[0].click().run()
    assert not app.exception
    for key in ("theme_radar_evidence_theme", "brief_provenance_theme"):
        assert app.session_state[key] == "B"
    assert app.session_state["brief_provenance_theme_user_selected"] is False


def test_unchanged_save_preserves_research_selection(tmp_path):
    app = _app(tmp_path / "watchlist.json")
    app.session_state["theme_radar_evidence_theme"] = "A"
    app.session_state["brief_provenance_theme"] = "B"
    app.session_state["brief_provenance_theme_user_selected"] = True
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["brief_provenance_theme"] == "B"
    assert app.session_state["theme_radar_evidence_theme"] == "A"
    assert app.session_state["brief_provenance_theme_user_selected"] is True


def test_failed_save_keeps_active_selection_and_allows_retry(tmp_path, monkeypatch):
    import src.watchlist_ui as ui

    path = tmp_path / "watchlist.json"
    original = json.dumps({"themes": ["A"]})
    path.write_text(original, encoding="utf-8")
    app = _app(path)
    app.session_state["theme_radar_evidence_theme"] = "A"
    app.session_state["brief_provenance_theme"] = "A"
    app.session_state["brief_provenance_theme_user_selected"] = True

    def fail_save(*args):
        raise OSError("private directory permission details")

    with monkeypatch.context() as patch:
        patch.setattr(ui, "save_personal_watchlist", fail_save)
        app.multiselect[0].set_value(["B"])
        app.button[0].click().run()
        assert not app.exception
        assert app.error
        assert not app.success
        assert "private directory" not in app.error[0].value
        assert json.loads(app.json[0].value)["themes"] == ["A"]
        assert path.read_text(encoding="utf-8") == original
        assert app.session_state["theme_radar_evidence_theme"] == "A"
        assert app.session_state["brief_provenance_theme"] == "A"
        assert app.session_state["brief_provenance_theme_user_selected"] is True

    app.button[0].click().run()
    assert not app.exception
    assert app.success
    assert json.loads(app.json[0].value)["themes"] == ["B"]
    assert app.session_state["theme_radar_evidence_theme"] == "B"
    assert app.session_state["brief_provenance_theme"] == "B"
    assert app.session_state["brief_provenance_theme_user_selected"] is False
    assert _app(path).multiselect[0].value == ["B"]
