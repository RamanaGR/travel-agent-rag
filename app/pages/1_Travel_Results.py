import logging
import os
import re
import sys

import streamlit as st

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(project_root)

from app.components.layout import render_trip_summary_bar, setup_page
from modules.attractions_api import fetch_attractions
from modules.rag_engine import index_exists, retrieve_for_trip
from modules.weather_api import get_forecast_summary, parse_forecast_to_days


def _display_name(name: str) -> str:
    """Strip TripAdvisor list numbering from attraction names."""
    if not name:
        return "Unknown attraction"
    return re.sub(r"^\d+\.\s*", "", name.strip())

setup_page("Travel Results", "📍", "preview")

st.title("Your Travel Results")
render_trip_summary_bar()

destination = st.session_state.get("destination")
budget = st.session_state.get("budget")
duration = st.session_state.get("duration")
date = st.session_state.get("date")
user_query = st.session_state.get("query", "")

if not all([destination, budget, duration, date]):
    st.error("Missing travel details. Please return to Home.")
    st.page_link("Home.py", label="Back to Home")
    st.stop()

try:
    duration_days = int(duration)
except (TypeError, ValueError):
    duration_days = 3

# --- Weather forecast ---
st.markdown("### Weather Forecast")
st.caption("OpenWeather provides a rolling 5-day forecast window from today.")
with st.spinner("Fetching multi-day forecast..."):
    weather_report = get_forecast_summary(destination, date, duration_days)
    forecast_days = parse_forecast_to_days(weather_report, duration_days)
    st.session_state.weather_report = weather_report
    st.session_state.forecast_days = forecast_days

weather_cols = st.columns(min(duration_days, 5))
for i, day in enumerate(forecast_days[: len(weather_cols)]):
    with weather_cols[i]:
        label = f"Day {day['day']}"
        temp_display = f"{day['temp']}°C" if day.get("temp") is not None else "—"
        st.metric(label, temp_display)
        summary = day.get("summary", "")
        if day.get("rain_warning"):
            st.markdown(f'<p class="rain-warning">{summary}</p>', unsafe_allow_html=True)
        else:
            st.caption(summary)

# --- RAG-ranked attractions ---
st.markdown("### Top Attractions")
st.caption("Ranked by hybrid search (semantic + keyword + quality signals). Select places to include in your itinerary.")

with st.spinner("Retrieving personalized attractions..."):
    api_attractions = fetch_attractions(destination)
    rag_results = []
    using_rag = st.session_state.get("rag_index_built", False)

    # Recover index flag if files exist but session was reset
    if not using_rag and index_exists(destination):
        using_rag = True
        st.session_state.rag_index_built = True
        st.session_state.index_city = destination

    if using_rag:
        rag_results = retrieve_for_trip(
            user_query=user_query,
            destination=destination,
            budget=budget,
            duration=duration,
            date=date,
            top_k=8,
        )

    if rag_results:
        display_attractions = rag_results
        st.success(f"Showing {len(display_attractions)} personalized picks for {destination}.")
    else:
        display_attractions = api_attractions[:8]
        st.warning(
            "Showing TripAdvisor order (RAG index not available). "
            "Add valid `OPENAI_API_KEY` and `RAPIDAPI_KEY` in `.env`, then submit a new plan on Home to build the index."
        )

if "selected_attractions" not in st.session_state:
    st.session_state.selected_attractions = display_attractions[:4]

selected_keys = set()
if st.session_state.selected_attractions:
    selected_keys = {
        (a.get("name"), a.get("link")) for a in st.session_state.selected_attractions
    }

placeholder_image = "https://via.placeholder.com/400x250?text=No+Image"
cols = st.columns(2)
new_selection = []

for i, att in enumerate(display_attractions):
    col = cols[i % 2]
    key = (att.get("name"), att.get("link"))
    default_checked = key in selected_keys or (not selected_keys and i < 4)

    with col:
        with st.container(border=True):
            name = _display_name(att.get("name", "Unknown"))
            checked = st.checkbox(
                f"Include in itinerary",
                value=default_checked,
                key=f"att_{i}",
            )
            st.markdown(f"#### {name}")
            if att.get("photo"):
                st.image(att.get("photo", placeholder_image), width="stretch")
            st.caption(f"Rating: {att.get('rating', 'N/A')} | Reviews: {att.get('reviews', 'N/A')}")
            category = att.get("category", "")
            if category:
                st.markdown(f"**Category:** {category}")
            reason = att.get("match_reason", "")
            score = att.get("retrieval_score", 0)
            if rag_results and reason and score > 0:
                st.markdown(
                    f'<span class="match-badge">{reason}</span> '
                    f'<span class="score-badge">{int(score * 100)}% match</span>',
                    unsafe_allow_html=True,
                )
            if att.get("link"):
                st.markdown(f"[View on TripAdvisor]({att['link']})")
            if checked:
                new_selection.append(att)

st.session_state.selected_attractions = new_selection

st.divider()
st.markdown("### Ready to Generate Your Itinerary?")
if not new_selection:
    st.warning("Select at least one attraction to include in your itinerary.")

nav_col1, nav_col2 = st.columns(2)
with nav_col1:
    if st.button("Generate Detailed Itinerary", type="primary", disabled=not new_selection):
        st.session_state.itinerary_generated = False
        st.session_state.itinerary_data = None
        st.switch_page("pages/2_Itinerary_Generator.py")
with nav_col2:
    st.page_link("Home.py", label="Back to Home")
