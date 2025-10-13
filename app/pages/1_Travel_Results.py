import os
import sys

import streamlit as st
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from modules.attractions_api import fetch_attractions
from modules.weather_api import get_weather
from modules.rag_engine import search_attractions
#current_dir = os.path.dirname(os.path.abspath(__file__))  # Gets /app/ dir
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
css_path = os.path.join(project_root, 'assets', 'style.css')
#css_path = os.path.join(current_dir, 'assets', 'style.css')  # Builds full path

# Load and inject CSS
with open(css_path, 'r') as f:
    css_content = f.read()

st.markdown(
    f"<style>{css_content}</style>",
    unsafe_allow_html=True
)


st.set_page_config(page_title="Your Travel Plan", page_icon="🧭", layout="wide")

# --- Validate session ---
if "destination" not in st.session_state:
    st.error("Please go to the Home page first.")
    st.stop()

destination = st.session_state["destination"]
budget = st.session_state["budget"]
duration = st.session_state["duration"]
date = st.session_state["date"]

# --- Header Section ---
st.markdown(f"# 🧭 Trip to **{destination}**")
st.write(f"🕓 Duration: {duration} days | 💰 Budget: ${budget} | 📅 Month: {date}")

st.divider()

# --- Weather Section ---
with st.container():
    st.markdown("### 🌤 Current Weather")
    with st.spinner("Fetching weather..."):
        weather = get_weather(destination)
        st.markdown(weather)

st.divider()

# --- Attractions Section ---
st.markdown("### 🗺️ Top Attractions")

cols = st.columns(2)
with st.spinner("Exploring attractions..."):
    attractions = fetch_attractions(destination)

if not attractions:
    st.warning("No attractions found for this location.")
else:
    for i, att in enumerate(attractions[:6], start=1):
        col = cols[i % 2]  # Alternate layout
        with col:
            with st.container():
                st.markdown(f"#### {i}. {att['name']}")
                st.caption(f"⭐ {att.get('rating', 'N/A')} | {att.get('reviews', 'N/A')} reviews")
                st.write(att.get("category", ""))
                if att.get("photo"):
                    st.image(att["photo"], use_container_width=True)
                if att.get("link"):
                    st.markdown(f"[View on TripAdvisor]({att['link']})")

st.divider()

# --- AI Recommendations ---
st.markdown("### 🤖 Smart Recommendations")

query = f"Top attractions for {destination}"
with st.spinner("Finding AI-curated experiences..."):
    results = search_attractions(query)

for i, res in enumerate(results[:3], start=1):
    st.markdown(f"**{i}. {res.get('name', 'Unknown')}** — {res.get('category', 'N/A')}")

st.page_link("pages/2_Itinerary_Generator.py", label="🧳 Generate Full Itinerary", icon="✨")
