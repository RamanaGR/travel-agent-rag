import os
import sys
import streamlit as st
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Create a logger for this module
logger = logging.getLogger(__name__)

# Append project root path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from modules.attractions_api import fetch_attractions
from modules.weather_api import get_weather
from modules.rag_engine import search_attractions

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
css_path = os.path.join(project_root, 'assets', 'style.css')

# Load and inject CSS
try:
    logger.debug("Loading CSS file")
    with open(css_path, 'r') as f:
        css_content = f.read()
    st.markdown(
        f"<style>{css_content}</style>",
        unsafe_allow_html=True
    )
    logger.info("✅ CSS loaded and injected successfully")
except Exception as e:
    logger.error(f"❌ Failed to load or inject CSS: {e}")
    st.warning(f"Could not load CSS: {e}")

# Ensure set_page_config is the first Streamlit command
try:
    logger.info("⚡ Setting Streamlit page configuration")
    st.set_page_config(page_title="Your Travel Plan", page_icon="🧭", layout="wide")
except Exception as e:
    logger.error(f"❌ Failed to set page config: {e}")
    st.error(f"Configuration error: {e}")
    raise

# Sidebar navigation
try:
    logger.debug("Rendering sidebar navigation")
    st.sidebar.subheader("Navigation")
    st.sidebar.page_link("Home.py", label="🏠 Home")
    st.sidebar.page_link("pages/1_Travel_Results.py", label="📍 Travel Results")
    st.sidebar.page_link("pages/2_Itinerary_Generator.py", label="🧳 Itinerary Generator")
    logger.info("✅ Sidebar navigation rendered")
except Exception as e:
    logger.error(f"❌ Failed to render sidebar: {e}")
    st.error(f"Sidebar rendering error: {e}")

# --- Validate session ---
logger.debug("Checking session state for required keys")
if "destination" not in st.session_state:
    logger.warning("🚫 Destination missing in session state. Redirecting to Home page.")
    st.error("Please go to the Home page first.")
    st.stop()

destination = st.session_state["destination"]
budget = st.session_state["budget"]
duration = st.session_state["duration"]
date = st.session_state["date"]
logger.info(f"Session state verified: destination={destination}, budget={budget}, duration={duration}, date={date}")

# --- Header Section ---
st.markdown(f"# 🧭 Trip to **{destination}**")
st.write(f"🕓 Duration: {duration} days | 💰 Budget: ${budget} | 📅 Month: {date}")
st.divider()
logger.info("Rendered header section")

# --- Weather Section ---
with st.container():
    st.markdown("### 🌤 Current Weather")
    with st.spinner("Fetching weather..."):
        logger.info(f"⚡ Fetching weather for {destination}")
        weather = get_weather(destination)
        logger.debug(f"Weather data received: {weather}")
        st.markdown(weather)
logger.info("✅ Weather section rendered")

st.divider()

# --- Attractions Section ---
st.markdown("### 🗺️ Top Attractions")
cols = st.columns(2)
with st.spinner("Exploring attractions..."):
    logger.info(f"⚡ Fetching attractions for {destination}")
    attractions = fetch_attractions(destination)
    logger.debug(f"Fetched {len(attractions)} attractions")

if not attractions:
    logger.warning(f"⚠️ No attractions found for {destination}")
    st.warning("No attractions found for this location.")
else:
    for i, att in enumerate(attractions[:6], start=1):
        col = cols[i % 2]
        with col:
            with st.container():
                st.markdown(f"#### {i}. {att['name']}")
                st.caption(f"⭐ {att.get('rating', 'N/A')} | {att.get('reviews', 'N/A')} reviews")
                st.write(att.get("category", ""))
                if att.get("photo"):
                    logger.debug(f"Rendering image for attraction {att['name']}")
                    st.image(att["photo"], use_container_width=True)
                if att.get("link"):
                    st.markdown(f"[View on TripAdvisor]({att['link']})")
                logger.debug(f"Rendered attraction {i}: {att['name']}")
logger.info("✅ Attractions section rendered")

st.divider()

# --- AI Recommendations ---
st.markdown("### 🤖 Smart Recommendations")
query = f"Top attractions for {destination}"
with st.spinner("Finding AI-curated experiences..."):
    logger.info(f"⚡ Fetching AI-curated attractions with query: {query}")
    results = []  # search_attractions(query, destination)
    logger.debug(f"AI-curated results: {len(results)} attractions")

for i, res in enumerate(results[:3], start=1):
    st.markdown(f"**{i}. {res.get('name', 'Unknown')}** — {res.get('category', 'N/A')}")
logger.info("✅ AI recommendations rendered")

st.page_link("pages/2_Itinerary_Generator.py", label="🧳 Generate Full Itinerary", icon="✨")
logger.info("✅ Itinerary generator link rendered")