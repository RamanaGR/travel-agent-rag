import logging
import os
import sys

import streamlit as st

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(project_root)

from app.components.layout import (
    THEMES,
    get_active_theme,
    render_theme_picker,
    save_default_theme,
    set_theme,
    setup_page,
)

setup_page("Theme Preview", "🎨", "plan")

# Theme picker in main area for live preview alongside gallery
render_theme_picker(location="main")

active = get_active_theme()
meta = THEMES[active]

st.title("Theme Preview")
st.caption(f"Currently previewing: **{meta['label']}** — {meta['description']}")

st.markdown("---")

# Color swatches
st.markdown("### Color palette")
swatch_cols = st.columns(4)
theme_swatches = {
    "ocean": [("#0EA5E9", "Primary"), ("#14B8A6", "Teal"), ("#FB7185", "Coral")],
    "sunset": [("#F97316", "Orange"), ("#A855F7", "Purple"), ("#FBBF24", "Gold")],
    "minimal": [("#6366F1", "Indigo"), ("#8B5CF6", "Violet"), ("#22D3EE", "Cyan")],
    "tropical": [("#10B981", "Emerald"), ("#84CC16", "Lime"), ("#FACC15", "Yellow")],
}
for col, (hex_color, name) in zip(swatch_cols, theme_swatches.get(active, theme_swatches["ocean"])):
    with col:
        st.markdown(
            f'<div class="theme-swatch">'
            f'<div class="theme-color-dot" style="background:{hex_color}"></div>'
            f'<div class="theme-swatch-title">{name}</div>'
            f'<span style="color:var(--text-muted)">{hex_color}</span></div>',
            unsafe_allow_html=True,
        )

st.markdown("### Components")

col1, col2 = st.columns(2)
with col1:
    st.markdown('<div class="step-pill active">1 Plan</div>', unsafe_allow_html=True)
    st.markdown('<div class="step-pill">2 Preview</div>', unsafe_allow_html=True)
    st.button("Primary button", type="primary")
    st.markdown(
        '<div class="example-card">Plan a <span class="keyword">4-day</span> trip to '
        '<span class="keyword">Miami</span> for under <span class="keyword">$1000</span>.</div>',
        unsafe_allow_html=True,
    )

with col2:
    st.metric("Destination", "Paris")
    st.metric("Budget", "$1,500")
    st.markdown(
        '<span class="match-badge">Matched: art, highly rated</span>'
        '<span class="score-badge">87% match</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="day-card"><b>Day 1: City Exploration</b><br>'
        "Morning museum visit, afternoon café, evening river walk.</div>",
        unsafe_allow_html=True,
    )

st.markdown("### All themes at a glance")
theme_cols = st.columns(len(THEMES))
for col, (tid, tmeta) in zip(theme_cols, THEMES.items()):
    with col:
        is_active = tid == active
        border = f"3px solid {tmeta['primary_color']}" if is_active else "1px solid #e2e8f0"
        st.markdown(
            f'<div class="theme-swatch" style="border:{border}">'
            f'<div class="theme-swatch-title">{tmeta["label"]}</div>'
            f'<p style="font-size:0.85rem">{tmeta["description"]}</p>'
            f'<div class="theme-color-dot" style="background:{tmeta["primary_color"]}"></div>'
            f"</div>",
            unsafe_allow_html=True,
        )
        if st.button(f"Apply {tmeta['label']}", key=f"preview_{tid}", width="stretch"):
            set_theme(tid)
            st.rerun()

st.markdown("---")
save_col1, save_col2 = st.columns([1, 3])
with save_col1:
    if st.button("Set as default theme", type="primary"):
        if save_default_theme(active):
            st.success(f"**{meta['label']}** is now your default theme.")
        else:
            st.error("Could not save theme preference.")

with save_col2:
    st.caption(
        "Default theme is saved to `.streamlit/theme_pref.toml` and used on next app launch. "
        "You can also set `UI_THEME=sunset` in your `.env` file as a fallback."
    )
