import logging
import os
import sys
from datetime import date as date_obj, datetime, timedelta

import streamlit as st

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_root)

from app.components.layout import setup_page
from modules.attractions_api import fetch_attractions
from modules.nlp_extractor import extract_entities
from modules.rag_engine import ensure_index_for_city, index_exists

setup_page("AI Travel Planner", "🌍", "plan")

EXAMPLES = [
    "Plan a 4-day trip to Miami starting tomorrow for under $1000.",
    "I need a 3-day itinerary for Paris starting from tomorrow.",
    "Las Vegas for the weekend with a $1500 budget.",
    "Show me things to do in Bangkok this week.",
]

st.title("Plan Your Next Adventure")
st.caption("Let AI craft your perfect trip based on budget, duration, and weather.")

st.markdown("### Example Inputs")

example_cols = st.columns(2)
for i, example in enumerate(EXAMPLES):
    with example_cols[i % 2]:
        if st.button(example, key=f"example_{i}", width="stretch"):
            st.session_state.travel_query = example

st.markdown("### Your Travel Plan")
if "travel_query" not in st.session_state:
    st.session_state.travel_query = ""

user_query = st.text_input(
    "Enter your plan:",
    key="travel_query",
    placeholder="e.g., Plan a 3-day trip to Paris this weekend",
)
col1, col2 = st.columns([1, 3])
with col1:
    generate = st.button("Generate Plan", type="primary")
with col2:
    st.caption("We'll extract your trip details and prepare personalized recommendations.")

if generate:
    if not user_query.strip():
        st.error("Please enter a travel request.")
        st.stop()

    with st.spinner("Analyzing your request..."):
        try:
            details = extract_entities(user_query)
        except Exception as e:
            logger.error("NLP extraction failed: %s", e)
            st.error("Error processing your query. Try a simpler format.")
            st.stop()

        destination = details.get("destination")
        budget = details.get("budget")
        duration = details.get("duration")
        date = details.get("date")

        validation_errors = []
        today = date_obj.today()
        max_date = today + timedelta(days=5)

        if not destination:
            validation_errors.append("No destination found. Please specify a city.")

        if not duration or duration < 1:
            validation_errors.append("Invalid duration. Use terms like '4-day' or 'weekend'.")

        if not budget or budget < 100:
            validation_errors.append("Invalid budget. Use terms like '$1000' or 'under $1500'.")

        if not date:
            date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
            validation_errors.append(f"No date provided. Defaulting to tomorrow ({date}).")
        else:
            try:
                parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
                if parsed_date < today:
                    validation_errors.append(f"Date {date} is in the past.")
                elif parsed_date > max_date:
                    date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
                    validation_errors.append(
                        f"Date is beyond the 5-day forecast. Defaulting to tomorrow ({date})."
                    )
            except ValueError:
                date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
                validation_errors.append(f"Invalid date format. Defaulting to tomorrow ({date}).")

        blocking = [e for e in validation_errors if "destination" in e.lower() or "duration" in e.lower() or "budget" in e.lower()]
        for error in validation_errors:
            st.warning(error)
        if blocking:
            st.stop()

        st.session_state.update({
            "query": user_query,
            "destination": destination,
            "budget": budget,
            "duration": duration,
            "date": date,
        })

    st.success(
        f"Destination: **{destination}** | Budget: **${budget}** | "
        f"Duration: **{duration} days** | Date: **{date}**"
    )

    with st.spinner(f"Fetching attractions and building search index for {destination}..."):
        st.session_state.index_building = True
        try:
            attractions = fetch_attractions(destination)
            if not attractions:
                st.warning("No attractions found. Continuing with limited recommendations.")
                st.session_state.rag_index_built = False
                st.session_state.index_city = None
            elif not index_exists(destination):
                built = ensure_index_for_city(destination, attractions, budget, duration)
                st.session_state.rag_index_built = built
                st.session_state.index_city = destination if built else None
            else:
                st.session_state.rag_index_built = True
                st.session_state.index_city = destination
        except Exception as e:
            logger.error("Index build failed: %s", e)
            st.warning(f"Could not build search index: {e}")
            st.session_state.rag_index_built = False
        finally:
            st.session_state.index_building = False

    if st.session_state.get("rag_index_built"):
        st.info(f"Search index ready for {destination}.")
    else:
        st.warning("Search index unavailable. Results will use API ordering.")

    st.switch_page("pages/1_Travel_Results.py")
