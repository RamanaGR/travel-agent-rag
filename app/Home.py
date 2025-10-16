import os
import sys
import streamlit as st
from datetime import datetime, date as date_obj, timedelta
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
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
from modules.nlp_extractor import extract_entities
from modules.rag_engine import load_and_normalize_data, build_embeddings, INDEX_FILE, META_FILE
from modules.attractions_api import fetch_attractions
from modules.weather_api_new import get_forecast_summary

current_dir = os.path.dirname(os.path.abspath(__file__))
css_path = os.path.join(current_dir, 'assets', 'style.css')

# Load and inject CSS
try:
    logger.debug("Loading CSS file")
    with open(css_path, 'r') as f:
        css_content = f.read()
    css_content += """
    .example-card {
        padding: 3px 5px;                     /* Less padding for tighter look */
        border: 1px solid #dcdcdc;             /* Softer border */
        border-radius: 3px;                    /* Slightly smaller corners */
        background-color: #fafafa;             /* Light gray background */
        margin-bottom: 3px;                    /* Reduced vertical spacing */
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);/* Subtle shadow */
        transition: all 0.2s ease-in-out;      /* Smooth hover transition */
    }
    .example-card:hover {
        box-shadow: 0 2px 4px rgba(0,0,0,0.1); /* Slight pop on hover */
    }
    .example-card span.keyword {
        font-weight: 300;
        color: #007bff;
    }

    /* Make sidebar text input clearly visible */
    section[data-testid="stSidebar"] input[type="text"] {
        border: 1.2px solid #4A90E2 !important;
        border-radius: 6px !important;
        padding: 5px 8px !important;
        background-color: #ffffff !important;
        color: #000000 !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
    }
    section[data-testid="stSidebar"] input[type="text"]:focus {
        border-color: #2E7D32 !important;
        box-shadow: 0 0 4px rgba(46, 125, 50, 0.4);
    }
    """

    st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    logger.info("✅ CSS loaded and injected successfully")
except Exception as e:
    logger.error(f"❌ Failed to load or inject CSS: {e}")
    st.warning(f"Could not load CSS: {e}")

# Ensure set_page_config is the first Streamlit command
try:
    logger.info("⚡ Setting Streamlit page configuration")
    st.set_page_config(
        page_title="AI Travel Planner",
        page_icon="🌍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
except Exception as e:
    logger.error(f"❌ Failed to set page config: {e}")
    st.error(f"Configuration error: {e}")
    raise

# Initialize session state
if 'rag_index_built' not in st.session_state:
    logger.debug("Checking RAG index files on startup")
    faiss_exists = os.path.exists(INDEX_FILE)
    meta_exists = os.path.exists(META_FILE)
    st.session_state.rag_index_built = faiss_exists and meta_exists
    st.session_state.index_city = None  # Initialize index_city
    logger.info(f"RAG index status: {'Built' if st.session_state.rag_index_built else 'Not Built'}")

# Sidebar setup
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

# --- RAG INDEX SETUP ---
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ RAG Index Control")

# City-specific index build
st.sidebar.markdown("### Build City-Specific Index")
city_for_index = st.sidebar.text_input("Enter City for Index Build")
build_index_button = st.sidebar.button("⚙️ Build Attraction Index for City", type="primary", disabled=not city_for_index.strip())

def build_rag_index_for_city(city):
    """Fetch attractions for city and build FAISS index."""
    logger.info(f"⚡ Starting city-specific RAG index build for {city}")
    st.session_state.rag_index_built = False
    st.session_state.index_city = None
    try:
        with st.spinner(f"Fetching attractions for {city}..."):
            logger.debug(f"Fetching attractions for {city}")
            attractions = fetch_attractions(city)
            if not attractions:
                raise ValueError(f"No attractions found for {city}")

        with st.spinner(f"Building vector index for {city} (may take 30-60 seconds)..."):
            logger.debug(f"Building FAISS index for {len(attractions)} attractions")
            build_embeddings(attractions)

        st.session_state.rag_index_built = True
        st.session_state.index_city = city
        st.success(f"✅ Attraction Index Built Successfully for {city}! You can now generate itineraries.")
        logger.info(f"✅ RAG index build completed for {city}")
    except Exception as e:
        logger.error(f"❌ Error building RAG index for {city}: {e}")
        st.session_state.rag_index_built = False
        st.session_state.index_city = None
        st.error(f"❌ Error building RAG index for {city}: {e}.")
        st.exception(e)

if build_index_button:
    logger.info(f"⚡ User triggered city-specific RAG index build for {city_for_index}")
    build_rag_index_for_city(city_for_index)

if st.session_state.rag_index_built and st.session_state.index_city:
    st.sidebar.success(f"Index Status: Built for {st.session_state.index_city}")
    logger.debug(f"RAG index status: Built for {st.session_state.index_city}")
else:
    st.sidebar.warning("Index Status: Not Built (Will use general knowledge)")
    logger.debug("RAG index status: Not Built")

# --- Title ---
st.title("🌍 Plan Your Next Adventure")
st.caption("Let AI craft your perfect trip based on budget, duration, and even weather constraints.")
logger.info("Rendered page title and caption")

# --- Examples Section ---
st.markdown("### 💡 Example Inputs")
st.info("Weather forecasts are available only for the next 5 days.", icon="ℹ️")
with st.expander("See example travel requests", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            """
            <div class="example-card">
                <b>Standard</b><br>
                Plan a <span class="keyword">4-day</span> trip to <span class="keyword">Miami</span> starting <span class="keyword">tomorrow</span> for under <span class="keyword">$1000</span>.
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown(
            """
            <div class="example-card">
                <b>Specific Date</b><br>
                I need a <span class="keyword">3-day</span> itinerary for <span class="keyword">Paris</span> starting from <span class="keyword">2025-10-17</span>.
            </div>
            """,
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            """
            <div class="example-card">
                <b>Minimal</b><br>
                <span class="keyword">Las Vegas</span> for <span class="keyword">the weekend</span> with a <span class="keyword">$1500 budget</span>.
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown(
            """
            <div class="example-card">
                <b>General</b><br>
                Show me things to do in <span class="keyword">Bangkok</span> <span class="keyword">this week</span>.
            </div>
            """,
            unsafe_allow_html=True
        )
logger.info("✅ Examples section rendered")

# --- User Input ---
st.markdown("### 📝 Your Travel Plan")
user_query = st.text_input("Enter your Plan:", placeholder="e.g., Plan a 3-day trip to Paris this weekend")
col1, col2 = st.columns([1, 3])
with col1:
    generate = st.button("✨ Generate Plan", type="primary")
with col2:
    st.caption("AI will extract details and prepare your plan instantly!")
logger.info("Rendered user input section")

# --- Handle Plan Generation ---
if generate:
    logger.info(f"⚡ User submitted query: '{user_query}'")
    if not user_query.strip():
        logger.warning("⚠️ Empty user query provided")
        st.error("Please enter a travel request, e.g., 'Plan a 4-day trip to Miami starting tomorrow for under $1000'.")
    else:
        with st.spinner("Analyzing your request..."):
            logger.debug("Extracting entities from user query")
            try:
                details = extract_entities(user_query)
            except Exception as e:
                logger.error(f"❌ NLP extraction failed: {e}")
                st.error("Error processing your query. Please try a simpler format, e.g., 'Plan a 4-day trip to Miami starting tomorrow for under $1000'.")
                st.stop()
            destination = details.get("destination")
            budget = details.get("budget")
            duration = details.get("duration")
            date = details.get("date")
            logger.info(f"Extracted details: destination={destination}, budget={budget}, duration={duration}, date={date}")

            # Input validation
            validation_errors = []
            today = date_obj.today()
            max_date = today + timedelta(days=5)

            # Destination validation
            if not destination:
                validation_errors.append("No destination found. Please specify a city, e.g., 'Miami' or 'Paris'.")
                logger.warning("⚠️ Validation failed: No destination extracted")

            # Duration validation
            if not duration or duration < 1:
                validation_errors.append("Invalid duration. Please specify a duration like '4-day' or 'weekend'.")
                logger.warning(f"⚠️ Validation failed: Invalid duration ({duration})")

            # Budget validation
            if not budget or budget < 100:
                validation_errors.append("Invalid budget. Please specify a budget like '$1000' or 'under $1500'.")
                logger.warning(f"⚠️ Validation failed: Invalid budget ({budget})")

            # Date validation
            if not date:
                logger.warning("⚠️ No date extracted, defaulting to tomorrow")
                date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
                validation_errors.append(
                    f"No date provided. Defaulting to tomorrow ({date}). Please specify a date like 'tomorrow' or '2025-10-17'."
                )
            else:
                try:
                    parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
                    if parsed_date < today:
                        validation_errors.append(
                            f"Date {date} is in the past. Please choose a date between {today.strftime('%Y-%m-%d')} and {max_date.strftime('%Y-%m-%d')}."
                        )
                        logger.warning(f"⚠️ Validation failed: Date {date} is in the past")
                    elif parsed_date > max_date:
                        logger.warning(f"⚠️ Date {date} is beyond 5-day forecast, defaulting to tomorrow")
                        validation_errors.append(
                            f"Date {date} is beyond the 5-day weather forecast limit. Defaulting to tomorrow ({today + timedelta(days=1):%Y-%m-%d})."
                        )
                        date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
                except ValueError:
                    logger.warning(f"⚠️ Invalid date format: {date}, defaulting to tomorrow")
                    validation_errors.append(
                        f"Invalid date format: '{date}'. Defaulting to tomorrow ({today + timedelta(days=1):%Y-%m-%d}). Please use YYYY-MM-DD or terms like 'tomorrow'."
                    )
                    date = (today + timedelta(days=1)).strftime('%Y-%m-%d')

            # Check RAG index compatibility
            index_city = st.session_state.get('index_city', None)
            if st.session_state.get('rag_index_built', False) and index_city and index_city.lower() != destination.lower():
                st.warning(
                    f"A RAG index is built for {index_city}, but your query is for {destination}. "
                    f"Please build an index for {destination} in the sidebar for optimal results."
                )
                logger.warning(f"⚠️ RAG index built for {index_city}, but query destination is {destination}")

            if validation_errors:
                for error in validation_errors:
                    st.error(error)
                st.info("Try an example like: 'Plan a 4-day trip to Miami starting tomorrow for under $1000'.")
                logger.error(f"❌ Validation failed with errors: {validation_errors}")
                # Allow proceeding with defaults if only date is invalid
                if len(validation_errors) == 1 and "date" in validation_errors[0].lower():
                    logger.info(f"✅ Proceeding with default date: {date}")
                else:
                    st.stop()

            st.session_state.update({
                "query": user_query,
                "destination": destination,
                "budget": budget,
                "duration": duration,
                "date": date,
            })
            logger.debug("Updated session state with extracted details")

        st.success(
            f"✅ Destination: **{destination}** | Budget: **${budget}** | Duration: **{duration} days** | Date: **{date}**"
        )
        st.balloons()
        logger.info("✅ Plan details rendered, switching to Travel Results page")
        st.switch_page("pages/1_Travel_Results.py")