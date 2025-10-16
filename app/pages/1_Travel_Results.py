import os
import sys
import streamlit as st
from datetime import datetime, timedelta
import logging

from modules.weather_api import get_weather

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

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)
from modules.attractions_api import fetch_attractions
from modules.weather_api_new import get_forecast_summary
from modules.rag_engine import search_attractions

# Load CSS
current_dir = os.path.dirname(os.path.abspath(__file__))
css_path = os.path.join(current_dir, '..', 'assets', 'style.css')
try:
    logger.debug("Loading CSS file")
    with open(css_path, 'r') as f:
        css_content = f.read()
    css_content += """
    /* Style for attraction images */
    .attraction-image {
        width: 250px;
        height: auto;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 10px;
        object-fit: cover;
        transition: transform 0.2s ease;
    }
    .attraction-image:hover {
        transform: scale(1.05);
    }
    /* Ensure responsive layout */
    .stImage {
        display: flex;
        justify-content: center;
    }
    """
    st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    logger.info("✅ CSS loaded and injected successfully")
except Exception as e:
    logger.error(f"❌ Failed to load or inject CSS: {e}")
    st.warning(f"Could not load CSS: {e}")

# Page config
try:
    logger.info("⚡ Setting Streamlit page configuration")
    st.set_page_config(
        page_title="Travel Results",
        page_icon="📍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
except Exception as e:
    logger.error(f"❌ Failed to set page config: {e}")
    st.error(f"Configuration error: {e}")
    raise

# Sidebar
try:
    logger.debug("Rendering sidebar")
    st.sidebar.image("app/assets/img.png", width='stretch')
    st.sidebar.markdown("### ✈️ AI Travel Planner")
    st.sidebar.caption("Personalized itineraries using Generative AI")
    # st.sidebar.markdown("---")
    # st.sidebar.subheader("🧭 Navigation")
    # st.sidebar.page_link("Home.py", label="🏠 Home")
    # st.sidebar.page_link("pages/1_Travel_Results.py", label="📍 Travel Results")
    # st.sidebar.page_link("pages/2_Itinerary_Generator.py", label="🧳 Itinerary Generator")
    logger.info("✅ Sidebar rendered successfully")
except Exception as e:
    logger.error(f"❌ Failed to render sidebar: {e}")
    st.error(f"Sidebar rendering error: {e}")

# Main content
st.title("📍 Your Travel Results")
st.caption(f"Exploring {st.session_state.get('destination', 'your destination')} with your preferences")
logger.info("Rendered page title and caption")

# Retrieve session state
destination = st.session_state.get("destination", None)
budget = st.session_state.get("budget", None)
duration = st.session_state.get("duration", None)
date = st.session_state.get("date", None)

if not all([destination, budget, duration, date]):
    logger.error("❌ Missing session state variables")
    st.error("Missing travel details. Please return to the Home page and enter a valid travel request.")
    st.page_link("Home.py", label="Back to Home")
    st.stop()

logger.info(f"⚡ Processing results for destination={destination}, budget={budget}, duration={duration}, date={date}")
# --- Weather Section ---
st.markdown("### 🌤 Weather Forecast")
with st.spinner("Fetching weather forecast..."):
    logger.info(f"⚡ Fetching weather forecast for {destination}")
    try:
        weather_summary = get_weather(destination)
        logger.debug(f"Weather summary received: {weather_summary}")
        st.text(weather_summary)
    except Exception as e:
        logger.error(f"❌ Failed to fetch weather forecast: {e}")
        st.error(f"Failed to fetch weather forecast: {e}")

# --- Attractions Section ---
st.markdown("### 🗺️ Top Attractions")
cols = st.columns(2)
with st.spinner("Exploring attractions..."):
    logger.info(f"⚡ Fetching attractions for {destination}")
    try:
        attractions = fetch_attractions(destination)
        logger.debug(f"Fetched {len(attractions)} attractions")
    except Exception as e:
        logger.error(f"❌ Failed to fetch attractions: {e}")
        attractions = []
        st.error(f"Failed to fetch attractions: {e}")

if not attractions:
    logger.warning(f"⚠️ No attractions found for {destination}")
    st.warning("No attractions found for this location.")
else:
    placeholder_image = "https://via.placeholder.com/250x150?text=No+Image+Available"
    for i, att in enumerate(attractions[:6], start=1):
        col = cols[i % 2]
        with col:
            with st.container():
                st.markdown(f"#### {i}. {att['name']}")
                st.caption(f"⭐ {att.get('rating', 'N/A')} | {att.get('reviews', 'N/A')} reviews")
                st.write(att.get("category", ""))
                image_url = att.get("photo", placeholder_image)
                try:
                    # Use HTML to apply custom CSS class
                    st.markdown(
                        f'<div class="stImage"><img src="{image_url}" class="attraction-image" alt="{att["name"]}"></div>',
                        unsafe_allow_html=True
                    )
                    logger.info(f"✅ Rendered image for attraction {att['name']}")
                except Exception as e:
                    logger.error(f"❌ Failed to render image for {att['name']}: {e}")
                    st.warning(f"Could not load image for {att['name']}")
                if att.get("link"):
                    st.markdown(f"[View on TripAdvisor]({att['link']})")
                logger.debug(f"Rendered attraction {i}: {att['name']}")
    logger.info("✅ Attractions section rendered")

st.divider()

# Navigation to Itinerary Generator
st.markdown("### 🧳 Ready to Generate Your Itinerary?")
if st.button("Generate Detailed Itinerary", type="primary"):
    logger.info("⚡ User navigated to Itinerary Generator")
    st.switch_page("pages/2_Itinerary_Generator.py")
st.page_link("Home.py", label="Back to Home")
logger.info("Rendered navigation section")