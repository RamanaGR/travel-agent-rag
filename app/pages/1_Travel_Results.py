import os
import sys
import streamlit as st
from datetime import datetime, timedelta
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

# Weather Forecast
st.markdown("### 🌤️ Weather Forecast")
try:
    with st.spinner("Fetching weather forecast..."):
        logger.debug(f"Fetching weather for {destination} starting {date}")
        weather_data = get_forecast_summary(destination, date, duration)
        if weather_data and isinstance(weather_data, list):
            st.write(f"**Weather in {destination} starting {date}:**")
            for day in weather_data:
                st.write(f"- **{day.get('date', 'Unknown')}**: {day.get('condition', 'N/A')} | Temp: {day.get('temp_min', 'N/A')}°C - {day.get('temp_max', 'N/A')}°C")
            logger.info("✅ Weather forecast rendered")
        else:
            st.warning(f"No weather data available for {destination}. Please check the city name or try again later.")
            logger.warning(f"⚠️ No weather data for {destination}")
except Exception as e:
    logger.error(f"❌ Error fetching weather: {e}")
    st.warning(f"Could not fetch weather data for {destination}: {e}. Proceeding with general recommendations.")

# Attractions
st.markdown("### 🏛️ Attractions")
try:
    with st.spinner("Fetching attractions..."):
        logger.debug(f"Fetching attractions for {destination}")
        index_city = st.session_state.get('index_city', None)
        if st.session_state.get('rag_index_built', False) and index_city and index_city.lower() == destination.lower():
            logger.debug("Using RAG index for attractions")
            attractions = fetch_attractions(destination, k=5)
        else:
            logger.debug("Using direct API call for attractions")
            if st.session_state.get('rag_index_built', False) and index_city:
                st.warning(
                    f"A RAG index is built for {index_city}, but your query is for {destination}. "
                    f"Please build an index for {destination} in the Home page for optimal results."
                )
                logger.warning(f"⚠️ RAG index built for {index_city}, but query destination is {destination}")
            attractions = fetch_attractions(destination)

        if attractions:
            cols = st.columns(3)  # Responsive grid with 3 columns
            placeholder_image = "https://via.placeholder.com/250x150?text=No+Image+Available"
            for idx, attraction in enumerate(attractions[:6]):  # Limit to 6 attractions
                with cols[idx % 3]:
                    logger.debug(f"Rendering attraction: {attraction.get('name', 'Unknown')}")
                    st.markdown(f"**{attraction.get('name', 'Unknown Attraction')}**")
                    image_url = attraction.get('image_url', placeholder_image)
                    try:
                        st.image(
                            image_url,
                            caption=attraction.get('name', 'Attraction'),
                            width='content',  # Replaced use_container_width=False
                            output_format="auto",
                            clamp=True,
                            channels="RGB",
                            extra_class="attraction-image"
                        )
                        logger.info(f"✅ Rendered image for {attraction.get('name')}")
                    except Exception as e:
                        logger.error(f"❌ Failed to render image for {attraction.get('name')}: {e}")
                        st.warning(f"Could not load image for {attraction.get('name', 'this attraction')}")
                    st.write(attraction.get('description', 'No description available'))
                    st.markdown("---")
            logger.info("✅ Attractions section rendered")
        else:
            st.warning(f"No attractions found for {destination}. Try building a RAG index in the Home page.")
            logger.warning(f"⚠️ No attractions found for {destination}")
except Exception as e:
    logger.error(f"❌ Error fetching attractions: {e}")
    st.error(f"Could not fetch attractions: {e}")

# Navigation to Itinerary Generator
st.markdown("### 🧳 Ready to Generate Your Itinerary?")
if st.button("Generate Detailed Itinerary", type="primary"):
    logger.info("⚡ User navigated to Itinerary Generator")
    st.switch_page("pages/2_Itinerary_Generator.py")
st.page_link("Home.py", label="Back to Home")
logger.info("Rendered navigation section")