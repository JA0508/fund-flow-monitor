from pathlib import Path

import streamlit as st

from src.watchlist import get_watchlist_themes, load_watchlist, save_personal_watchlist


def render_personal_watchlist(default: dict, options: list[str], path: Path, *, enabled: bool) -> dict:
    if not enabled:
        return default
    current = load_watchlist(str(path)) if path.exists() else default
    with st.sidebar.expander("个人关注", expanded=False):
        st.caption("仅供本机单人使用；不适用于多人共享部署。")
        if current.get("_load_warning"):
            st.warning(current["_load_warning"])
        selected = get_watchlist_themes(current)
        if any(theme not in options for theme in selected):
            st.warning("已保存的部分主题不在当前分类中；重新保存会移除这些主题。")
        selection_key = "personal_watchlist_selection"
        if selection_key not in st.session_state:
            st.session_state[selection_key] = [t for t in selected if t in options]
        with st.form("personal_watchlist_form"):
            themes = st.multiselect("关注主题", options, key=selection_key)
            submitted = st.form_submit_button("保存关注")
        if submitted:
            try:
                save_personal_watchlist(path, themes, options)
            except (OSError, ValueError):
                st.error("保存失败，原关注配置未更新。请检查主题选择和本地目录权限。")
            else:
                if list(themes) != selected:
                    # Explicit values prevent frontend widget state restoring the old theme.
                    for key in ("theme_radar_evidence_theme", "brief_provenance_theme"):
                        st.session_state[key] = themes[0] if themes else None
                    st.session_state["brief_provenance_theme_user_selected"] = False
                st.success("关注已保存，下次打开将恢复。")
                return {"watchlist_name": "个人关注主题", "themes": list(themes)}
    return current
