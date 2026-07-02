"""Shared Streamlit layout components."""

import os
from pathlib import Path

import streamlit as st

try:
    from config.config import (
        OPENAI_API_KEY,
        OPENWEATHER_KEY,
        RAPIDAPI_KEY,
        UI_THEME,
        USE_OFFLINE_MODE,
    )
except ImportError:
    OPENAI_API_KEY = None
    OPENWEATHER_KEY = None
    RAPIDAPI_KEY = None
    UI_THEME = "sunset"
    USE_OFFLINE_MODE = False

STEPS = [
    ("plan", "Plan", "Home.py"),
    ("preview", "Attractions", "pages/1_Travel_Results.py"),
    ("itinerary", "Itinerary", "pages/2_Itinerary_Generator.py"),
]

TRIP_SESSION_KEYS = (
    "query",
    "travel_query",
    "destination",
    "budget",
    "duration",
    "date",
    "rag_index_built",
    "index_city",
    "index_building",
    "selected_attractions",
    "weather_report",
    "forecast_days",
    "itinerary_generated",
    "itinerary_data",
)

THEMES = {
    "ocean": {
        "label": "Ocean Breeze",
        "file": "ocean.css",
        "description": "Fresh coastal teal, sky blue, and coral",
        "primary_color": "#0EA5E9",
    },
    "sunset": {
        "label": "Sunset Wanderlust",
        "file": "sunset.css",
        "description": "Bold orange, purple, and gold gradients",
        "primary_color": "#F97316",
    },
    "minimal": {
        "label": "Modern Minimal",
        "file": "minimal.css",
        "description": "Clean indigo, violet, and cyan accents",
        "primary_color": "#6366F1",
    },
    "tropical": {
        "label": "Tropical Passport",
        "file": "tropical.css",
        "description": "Vibrant emerald, lime, and sunny yellow",
        "primary_color": "#10B981",
    },
}

THEME_WIDGET_KEYS = {
    "sidebar": "theme_selector_sidebar",
    "main": "theme_selector_main",
    "inline": "theme_selector_inline",
}


def _widget_key(location: str) -> str:
    return THEME_WIDGET_KEYS.get(location, THEME_WIDGET_KEYS["main"])


def set_theme(theme_id: str) -> bool:
    """Set active theme; widget selectors sync on the next run."""
    if theme_id not in THEMES:
        return False
    st.session_state.ui_theme = theme_id
    st.session_state["_pending_theme_sync"] = theme_id
    return True


THEME_PREF_FILE = Path(__file__).resolve().parents[2] / ".streamlit" / "theme_pref.toml"


def _assets_dir():
    return os.path.join(os.path.dirname(__file__), "..", "assets")


def _themes_dir():
    return os.path.join(_assets_dir(), "themes")


def load_saved_theme() -> str:
    """Load persisted theme id from .streamlit/theme_pref.toml."""
    if not THEME_PREF_FILE.exists():
        return UI_THEME if UI_THEME in THEMES else "sunset"
    try:
        content = THEME_PREF_FILE.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("theme_id") and "=" in line:
                theme_id = line.split("=", 1)[1].strip().strip('"').strip("'")
                if theme_id in THEMES:
                    return theme_id
    except OSError:
        pass
    return UI_THEME if UI_THEME in THEMES else "sunset"


def save_default_theme(theme_id: str) -> bool:
    """Persist theme as default for future sessions."""
    if theme_id not in THEMES:
        return False
    THEME_PREF_FILE.parent.mkdir(parents=True, exist_ok=True)
    THEME_PREF_FILE.write_text(f'theme_id = "{theme_id}"\n', encoding="utf-8")
    return True


def init_theme():
    """Initialize theme in session state from saved pref or env."""
    if "ui_theme" not in st.session_state:
        st.session_state.ui_theme = load_saved_theme()


def get_active_theme() -> str:
    """Return current theme id."""
    init_theme()
    theme = st.session_state.get("ui_theme", "sunset")
    return theme if theme in THEMES else "sunset"


def load_css(theme_id: str | None = None):
    """Load base stylesheet, Google Fonts, and theme overrides."""
    if theme_id is None:
        theme_id = get_active_theme()

    fonts = (
        "@import url('https://fonts.googleapis.com/css2?"
        "family=Open+Sans:wght@400;600&family=Poppins:wght@600;700&display=swap');"
    )
    css_parts = [fonts]

    base_path = os.path.join(_assets_dir(), "style.css")
    try:
        with open(base_path, "r", encoding="utf-8") as f:
            css_parts.append(f.read())
    except OSError as e:
        st.warning(f"Could not load base CSS: {e}")

    theme_file = THEMES.get(theme_id, THEMES["sunset"])["file"]
    theme_path = os.path.join(_themes_dir(), theme_file)
    try:
        with open(theme_path, "r", encoding="utf-8") as f:
            css_parts.append(f.read())
    except OSError as e:
        st.warning(f"Could not load theme CSS: {e}")

    st.markdown(f"<style>{''.join(css_parts)}</style>", unsafe_allow_html=True)


def render_theme_picker(location: str = "sidebar"):
    """Render theme selector; keeps ui_theme in sync with widget state."""
    init_theme()
    labels = {tid: meta["label"] for tid, meta in THEMES.items()}
    options = list(THEMES.keys())

    if st.session_state.ui_theme not in options:
        st.session_state.ui_theme = load_saved_theme()

    widget_key = _widget_key(location)
    if st.session_state.get("_pending_theme_sync"):
        st.session_state[widget_key] = st.session_state["_pending_theme_sync"]
        del st.session_state["_pending_theme_sync"]
    elif widget_key not in st.session_state:
        st.session_state[widget_key] = st.session_state.ui_theme

    picker_kwargs = {
        "label": "Color theme",
        "options": options,
        "format_func": lambda x: labels[x],
        "key": widget_key,
    }

    if location == "sidebar":
        st.sidebar.selectbox(**picker_kwargs)
    elif location == "inline":
        st.selectbox(**picker_kwargs)
    else:
        st.radio(
            "Choose a theme",
            options=options,
            format_func=lambda x: labels[x],
            horizontal=True,
            key=widget_key,
        )

    st.session_state.ui_theme = st.session_state[widget_key]
    return st.session_state.ui_theme


def clear_trip_session():
    """Reset trip-related session state for a fresh plan."""
    for key in TRIP_SESSION_KEYS:
        st.session_state.pop(key, None)


def _step_index(step_id: str) -> int:
    for i, (sid, _, _) in enumerate(STEPS):
        if sid == step_id:
            return i
    return -1


def _step_accessible(step_id: str) -> bool:
    if step_id == "plan":
        return True
    if step_id == "preview":
        return bool(st.session_state.get("destination"))
    if step_id == "itinerary":
        return bool(st.session_state.get("destination"))
    return False


def _step_state(step_id: str, current_step: str) -> str:
    current_idx = _step_index(current_step)
    step_idx = _step_index(step_id)
    if step_idx < 0:
        return "locked"
    if step_id == current_step:
        return "active"
    if step_idx < current_idx:
        return "done"
    if not _step_accessible(step_id):
        return "locked"
    return "default"


def _key_configured(key: str | None) -> bool:
    if not key:
        return False
    lowered = key.strip().lower()
    return not (lowered.startswith("your_") or lowered in ("", "none", "null"))


def _system_status_rows() -> list[tuple[str, str, str]]:
    """Return (label, status_class, detail) for system health."""
    rows = []
    if USE_OFFLINE_MODE:
        rows.append(("Offline mode", "warn", "Using cached data only"))
    openai_ok = _key_configured(OPENAI_API_KEY)
    rows.append((
        "OpenAI",
        "ok" if openai_ok else "error",
        "Embeddings & itinerary" if openai_ok else "Set OPENAI_API_KEY in .env",
    ))
    rapid_ok = _key_configured(RAPIDAPI_KEY)
    rows.append((
        "RapidAPI",
        "ok" if rapid_ok else "error",
        "Attractions" if rapid_ok else "Set RAPIDAPI_KEY in .env",
    ))
    weather_ok = _key_configured(OPENWEATHER_KEY)
    rows.append((
        "OpenWeather",
        "ok" if weather_ok else "error",
        "Forecasts" if weather_ok else "Set OPENWEATHER_KEY in .env",
    ))
    destination = st.session_state.get("destination")
    if destination:
        if st.session_state.get("index_building"):
            rows.append(("Search index", "warn", f"Building for {destination}…"))
        elif st.session_state.get("rag_index_built"):
            rows.append(("Search index", "ok", f"Ready for {destination}"))
        else:
            rows.append(("Search index", "warn", "API fallback ranking"))
    return rows


def render_brand():
    """Compact sidebar brand header."""
    st.sidebar.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-mark">TF</div>
            <div class="sidebar-brand-text">
                <span class="sidebar-brand-name">TripForge</span>
                <span class="sidebar-brand-tag">AI Travel Planner</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_nav(current_step: str):
    """Vertical step navigation with active, done, and locked states."""
    st.sidebar.markdown('<p class="sidebar-section-label">Your journey</p>', unsafe_allow_html=True)
    markers = {"active": "●", "done": "✓", "default": "○", "locked": "○"}

    for step_id, label, page in STEPS:
        state = _step_state(step_id, current_step)
        marker = markers[state]

        if state == "locked":
            st.sidebar.markdown(
                f'<div class="sidebar-nav-item locked">'
                f'<span class="nav-marker">{marker}</span>'
                f'<span class="nav-label">{label}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
        elif state == "active":
            st.sidebar.markdown(
                f'<div class="sidebar-nav-item active">'
                f'<span class="nav-marker">{marker}</span>'
                f'<span class="nav-label">{label}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.sidebar.page_link(page, label=label)


def render_how_it_works():
    """Onboarding hints when no trip exists yet."""
    st.sidebar.markdown(
        """
        <div class="sidebar-hint-card">
            <p class="sidebar-section-label">How it works</p>
            <ol class="sidebar-hint-list">
                <li>Describe your trip on Home</li>
                <li>Pick attractions & check weather</li>
                <li>Generate your itinerary</li>
            </ol>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _index_status_pill() -> tuple[str, str]:
    if st.session_state.get("index_building"):
        return "warn", "Building index…"
    if st.session_state.get("rag_index_built"):
        city = st.session_state.get("index_city") or st.session_state.get("destination", "")
        return "ok", f"Index ready · {city}"
    return "warn", "API fallback ranking"


def render_trip_passport():
    """Trip summary card with status pills and quick actions."""
    destination = st.session_state.get("destination")
    if not destination:
        return

    budget = st.session_state.get("budget")
    duration = st.session_state.get("duration")
    date = st.session_state.get("date")
    selected = st.session_state.get("selected_attractions") or []
    index_class, index_label = _index_status_pill()

    meta_parts = []
    if duration:
        meta_parts.append(f"{duration}d")
    if budget:
        try:
            meta_parts.append(f"${int(budget):,}")
        except (TypeError, ValueError):
            meta_parts.append(f"${budget}")
    if date:
        meta_parts.append(date)
    meta_line = " · ".join(meta_parts) if meta_parts else "Trip details"

    st.sidebar.markdown(
        f"""
        <div class="trip-passport">
            <p class="sidebar-section-label">Trip passport</p>
            <p class="passport-destination">{destination}</p>
            <p class="passport-meta">{meta_line}</p>
            <div class="passport-pills">
                <span class="status-pill {index_class}">{index_label}</span>
                <span class="status-pill neutral">{len(selected)} selected</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    action_col1, action_col2 = st.sidebar.columns(2)
    with action_col1:
        if st.button("Edit plan", key="sidebar_edit_plan", width="stretch"):
            if st.session_state.get("query"):
                st.session_state.travel_query = st.session_state["query"]
            st.switch_page("Home.py")
    with action_col2:
        if st.button("New trip", key="sidebar_new_trip", width="stretch"):
            clear_trip_session()
            st.switch_page("Home.py")


def render_sidebar_cta(current_step: str):
    """Page-specific call-to-action in the sidebar."""
    if current_step == "preview":
        selected = st.session_state.get("selected_attractions") or []
        count = len(selected)
        st.sidebar.markdown('<p class="sidebar-section-label">Next step</p>', unsafe_allow_html=True)
        if st.sidebar.button(
            f"Continue to itinerary ({count})",
            type="primary",
            disabled=count == 0,
            width="stretch",
            key="sidebar_continue_itinerary",
        ):
            st.session_state.itinerary_generated = False
            st.session_state.itinerary_data = None
            st.switch_page("pages/2_Itinerary_Generator.py")
    elif current_step == "itinerary":
        st.sidebar.markdown('<p class="sidebar-section-label">Navigate</p>', unsafe_allow_html=True)
        if st.sidebar.button("Back to attractions", width="stretch", key="sidebar_back_results"):
            st.switch_page("pages/1_Travel_Results.py")


def render_appearance_expander():
    """Theme and preview controls tucked in a collapsed expander."""
    with st.sidebar.expander("Appearance", expanded=False):
        render_theme_picker(location="inline")
        st.caption(f"Active: {THEMES[get_active_theme()]['label']}")
        st.page_link("pages/0_Theme_Preview.py", label="Open theme gallery")


def render_system_status_expander():
    """API and index health indicators."""
    with st.sidebar.expander("System status", expanded=False):
        for label, status_class, detail in _system_status_rows():
            st.markdown(
                f'<div class="status-row">'
                f'<span class="status-dot {status_class}"></span>'
                f'<span class="status-row-label">{label}</span>'
                f'<span class="status-row-detail">{detail}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )


def render_sidebar_footer():
    """Muted footer line."""
    st.sidebar.markdown(
        """
        <p class="sidebar-footer">Powered by RAG + Generative AI</p>
        <p class="sidebar-info-hint">Weather forecasts cover the next 5 days only.</p>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(current_step: str = "plan"):
    """Trip Command Panel — brand, navigation, passport, settings."""
    render_brand()
    render_step_nav(current_step)

    destination = st.session_state.get("destination")
    if destination:
        render_trip_passport()
        render_sidebar_cta(current_step)
    else:
        render_how_it_works()

    render_appearance_expander()
    render_system_status_expander()
    render_sidebar_footer()


def render_trip_summary_bar():
    """Render trip summary metrics across preview/itinerary pages."""
    destination = st.session_state.get("destination")
    budget = st.session_state.get("budget")
    duration = st.session_state.get("duration")
    date = st.session_state.get("date")
    if not destination:
        return

    cols = st.columns(4)
    cols[0].metric("Destination", destination)
    cols[1].metric("Budget", f"${budget}" if budget else "—")
    cols[2].metric("Duration", f"{duration} days" if duration else "—")
    cols[3].metric("Start date", date or "—")


def setup_page(
    page_title: str,
    page_icon: str,
    current_step: str,
):
    """Configure page, load CSS, and Trip Command Panel sidebar."""
    sidebar_state = "collapsed" if current_step in ("preview", "itinerary") else "expanded"
    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state=sidebar_state,
    )
    init_theme()
    render_sidebar(current_step)
    load_css(get_active_theme())
