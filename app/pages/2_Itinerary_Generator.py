import os
import re
import streamlit as st
import sys
import json
from datetime import datetime, timedelta
import logging

# Configure logging to match weather_api_new.py
logging.basicConfig(
    level=logging.INFO,  # INFO for production; change to DEBUG for detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Output to console for Streamlit Cloud
    ]
)

# Create a logger for this module
logger = logging.getLogger(__name__)

# Append project root path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from openai import OpenAI
from modules.rag_engine import search_attractions
from config.config import OPENAI_API_KEY
from modules.weather_api_new import get_forecast_summary

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
    st.set_page_config(page_title="AI Itinerary Generator", page_icon="🧳", layout="wide")
except Exception as e:
    logger.error(f"❌ Failed to set page config: {e}")
    st.error(f"Configuration error: {e}")
    raise

# Sidebar navigation
# try:
#     logger.debug("Rendering sidebar navigation")
#     st.sidebar.subheader("Navigation")
#     st.sidebar.page_link("Home.py", label="🏠 Home")
#     st.sidebar.page_link("pages/1_Travel_Results.py", label="📍 Travel Results")
#     st.sidebar.page_link("pages/2_Itinerary_Generator.py", label="🧳 Itinerary Generator")
#     logger.info("✅ Sidebar navigation rendered")
# except Exception as e:
#     logger.error(f"❌ Failed to render sidebar: {e}")
#     st.error(f"Sidebar rendering error: {e}")

# --- Verify context ---
logger.debug("Checking session state for required keys")
if "destination" not in st.session_state:
    logger.warning("🚫 Destination missing in session state. Redirecting to Home page.")
    st.error("Please go to the Home page first.")
    st.stop()
destination = st.session_state["destination"]
budget = st.session_state["budget"]
duration = st.session_state["duration"]
date = st.session_state["date"]
rag_index_built = st.session_state.get('rag_index_built', False)
logger.info(f"Session state verified: destination={destination}, budget={budget}, duration={duration}, date={date}, rag_index_built={rag_index_built}")

# Calculate integer duration for API call and LLM prompt
duration_days = 3  # Default value
try:
    duration_days = int(duration)
    logger.debug(f"Parsed duration as integer: {duration_days} days")
except ValueError:
    # If duration is text (e.g., 'a week'), default to 7 days.
    if isinstance(duration, str) and 'week' in duration.lower():
        duration_days = 7
    logger.warning(f"⚠️ Could not parse duration '{duration}'. Defaulting to {duration_days} days.")
    st.warning(f"Could not parse duration '{duration}'. Defaulting to {duration_days} days.")

# Calculate start date for weather API (requires YYYY-MM-DD format)
try:
    logger.debug(f"Parsing date: {date}")
    if len(date.split('-')) == 3:  # YYYY-MM-DD format
        start_date = datetime.strptime(date, '%Y-%m-%d').date()
    else:  # Month YYYY format
        start_date = datetime.strptime(date, '%B %Y').date()
    start_date_str = start_date.strftime('%Y-%m-%d')
    logger.info(f"✅ Start date parsed: {start_date_str}")
except Exception as e:
    logger.error(f"❌ Error parsing date '{date}': {e}. Defaulting to today.")
    st.error(f"Error parsing date '{date}': {e}. Defaulting to today.")
    start_date = datetime.now().date()
    start_date_str = start_date.strftime('%Y-%m-%d')

st.title(f"🧳 {duration_days}-Day Itinerary for {destination}")
st.markdown(f"**Budget:** ${budget} | **Start Date:** {start_date} | **Duration:** {duration_days} Days")
st.divider()
logger.info("Rendered page title and trip details")

# Initialize OpenAI client
try:
    logger.debug("Initializing OpenAI client")
    client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("✅ OpenAI client initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize OpenAI client: {e}")
    st.error(f"OpenAI initialization error: {e}")
    st.stop()

# --------------------------------------------------------------------------
# --- STEP 1/3: Fetch Forecast for Constraint Validation ---
# --------------------------------------------------------------------------
weather_lookup = {}
with st.spinner("Step 1/3: Fetching multi-day weather forecast for planning..."):
    logger.info(f"⚡ Fetching weather forecast for {destination}, start_date={start_date_str}, duration={duration_days}")
    weather_report = get_forecast_summary(destination, start_date_str, duration_days)
    logger.debug(f"Weather report received: {weather_report}")

    # Build weather lookup table
    for i in range(duration_days):
        day_tag = f"Day {i + 1}"
        line = next((line for line in weather_report.split('\n') if line.startswith(day_tag)), None)
        if line:
            weather_lookup[i + 1] = line.split(': ')[-1]
            logger.debug(f"Weather lookup for Day {i + 1}: {weather_lookup[i + 1]}")
        else:
            weather_lookup[i + 1] = "Details unavailable."
            logger.warning(f"⚠️ No weather data for Day {i + 1}")

    if "unavailable" in weather_report or "limit reached" in weather_report or not weather_report:
        logger.warning(f"⚠️ Weather forecast limited: {weather_report}")
        st.warning(f"⚠️ Weather constraint validation limited. Raw report: {weather_report}. Proceeding with best-effort planning.")
        weather_report = "Weather data is unavailable for constraint validation."
    else:
        logger.info("✅ Weather forecast fetched successfully")
        st.success("✅ Multi-day weather forecast secured for constraint validation.")

# -------------------------------------------------------------
# --- STEP 2/3: Retrieve context data (RAG Call) ---
# -------------------------------------------------------------
with st.spinner("Step 2/3: Gathering top attractions..."):
    logger.info("⚡ Fetching top attractions via RAG")
    if not rag_index_built:
        logger.warning("⚠️ RAG index not built. Using LLM general knowledge.")
        st.warning("Index not built. Using LLM general knowledge for attractions.")
        top_places = []
    else:
        query = f"Top attractions for {destination} that fit a {budget} budget"
        logger.debug(f"RAG query: {query}")
        top_places = search_attractions(query, destination, top_k=6)
        logger.debug(f"RAG returned {len(top_places)} attractions")

    if not top_places:
        summary = "No specific, high-relevance attractions found."
        logger.info("No attractions found by RAG")
    else:
        attraction_summaries = []
        for p in top_places:
            attraction_summaries.append(
                f"- {p.get('name', 'Unknown')}: {p.get('description', 'No description.')} "
                f"(Category: {p.get('category', 'N/A')}, Rating: {p.get('rating', 'N/A')})"
            )
        summary = "\n".join(attraction_summaries)
        logger.info(f"✅ Attraction summaries generated: {len(attraction_summaries)} attractions")
    st.success("✅ Attraction data fetched.")

# -------------------------------------------------------------
# --- STEP 3/3: LLM Call to Generate Itinerary ---
# -------------------------------------------------------------
system_prompt = f"""
You are an expert travel agent specializing in creating detailed, day-by-day travel itineraries. 
Your response MUST be a single, complete JSON object.

The user's trip details are:
- DESTINATION: {destination}
- DURATION: {duration_days} days
- START DATE: {start_date_str}
- BUDGET: ${budget}
- WEATHER FORECAST: {weather_report}

Your plan MUST strictly adhere to the budget, duration, and weather constraints. Use the provided attraction data for inspiration and context.

**Constraint Adherence Rules:**
1.  **BUDGET:** The 'total_trip_spend' in the final JSON MUST NOT exceed the user's budget of ${budget}. Ensure daily costs sum up correctly.
2.  **DURATION:** The 'itinerary' array MUST contain exactly {duration_days} day objects.
3.  **WEATHER:** Recommend indoor or covered activities for days with rain/snow warnings in the forecast.

**Attraction Context (for inspiration, not exhaustive):**
{summary}

**JSON Output Format:**
{{
  "destination": "{destination}",
  "duration_days": {duration_days},
  "budget": {budget},
  "total_trip_spend": <float: Calculate the total cost of all activities>,
  "notes": "<string: A summary of the plan, including weather considerations and a quick check on budget adherence>",
  "itinerary": [
    {{
      "day_title": "Day 1: <Descriptive Title>",
      "daily_spend": <float: Total cost for this day>,
      "date": "{start_date_str}",
      "activities": [
        {{
          "time_slot": "Morning",
          "activity": "<Activity Name and brief description>",
          "cost": <float: Estimated cost of activity>
        }},
        {{
          "time_slot": "Afternoon",
          "activity": "<Activity Name and brief description>",
          "cost": <float: Estimated cost of activity>
        }},
        {{
          "time_slot": "Evening",
          "activity": "<Dinner/Night activity>",
          "cost": <float: Estimated cost of activity>
        }}
      ]
    }},
    // ... Repeat for all {duration_days} days ...
  ]
}}
"""

user_prompt = f"Generate the full {duration_days}-day travel itinerary for {destination}, starting on {start_date_str}, with a budget of ${budget}."

st.markdown("### 🤖 AI Generating Itinerary...")
placeholder = st.empty()
logger.info("⚡ Calling LLM to generate itinerary")

try:
    with st.spinner("Step 3/3: Calling LLM to synthesize the plan..."):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
    json_text = response.choices[0].message.content
    itinerary_data = json.loads(json_text)
    logger.info("✅ Itinerary generated successfully")
    st.success("✅ Itinerary Generated!")

except Exception as e:
    logger.error(f"❌ Error during LLM itinerary generation: {e}")
    st.error("An error occurred during AI generation. Please check your API key or try again.")
    st.exception(e)
    st.stop()

# -------------------------------------------------------------
# --- Display and Download Output ---
# -------------------------------------------------------------
logger.debug("Rendering itinerary display")
# Safety check for total spend and budget
total_trip_spend = itinerary_data.get("total_trip_spend", 0.0)
logger.debug(f"Total trip spend: ${total_trip_spend}, Budget: ${budget}")

# Display the Itinerary
st.markdown("### 🗺️ Day-by-Day Plan")
day_plans = itinerary_data.get("itinerary", [])
current_date = start_date

for day_index, day_plan in enumerate(day_plans):
    # Calculate the actual date for display
    day_date = current_date + timedelta(days=day_index)
    day_date_str = day_date.strftime('%B %d, %Y')
    weather_info = weather_lookup.get(day_index + 1, "Weather unavailable.")
    logger.debug(f"Rendering Day {day_index + 1}: {day_date_str}, Weather: {weather_info}")

    # Title with date and daily spend
    st.subheader(f"{day_plan.get('day_title', f'Day {day_index + 1}')}")
    st.markdown(
        f"🗓️ **Date:** {day_date_str} | 💰 **Daily Spend:** ${day_plan.get('daily_spend', 0.0):.2f} | 🌤 **Weather:** {weather_info}")
    logger.debug(f"Rendered Day {day_index + 1} header")

    # Display activities
    for activity in day_plan.get("activities", []):
        time_slot = activity.get('time_slot', 'Activity')
        activity_desc = activity.get('activity', 'No activity details.')
        cost = activity.get('cost', 0.0)
        icon = "☀️" if "Morning" in time_slot else ("🌆" if "Afternoon" in time_slot else "🌙")
        st.markdown(
            f"""
            <div style='background-color:#f9fafb;padding:15px;border-radius:10px;margin-bottom:10px;'>
                <b>{icon} {time_slot}</b><br>{activity_desc} (Cost: ${cost:.2f})
            </div>
            """,
            unsafe_allow_html=True,
        )
    logger.debug(f"Rendered activities for Day {day_index + 1}")
    st.markdown("---")

# --- Summary and Notes ---
st.markdown("### 📝 Summary and Notes")
notes = itinerary_data.get("notes", "No specific notes provided by the AI.").replace('*', '')
st.markdown(f"**Total Trip Spend:** **${total_trip_spend:.2f}** (Budget: ${budget})")
st.info(notes)
st.divider()
logger.info("✅ Summary and notes rendered")

# Convert JSON to string for download
download_json = json.dumps(itinerary_data, indent=2)
logger.debug("Prepared JSON itinerary for download")

st.download_button(
    label="📥 Download Itinerary (JSON)",
    data=download_json,
    file_name=f"{destination}_itinerary.json",
    mime="application/json"
)
logger.debug("Rendered JSON download button")

# Prepare plain text for download
download_text = f"ITINERARY FOR {destination}\nTotal Budget: ${budget}\nTotal Spend: ${total_trip_spend:.2f}\n\n"
for day_plan in itinerary_data.get("itinerary", []):
    day_num = day_plans.index(day_plan) + 1
    weather_info = weather_lookup.get(day_num, "Weather details unavailable.")
    day_date = start_date + timedelta(days=day_num - 1)
    day_date_str = day_date.strftime('%B %d, %Y')
    download_text += f"--- {day_plan['day_title']} ({day_date_str}) | Total: ${day_plan['daily_spend']:.2f} | Weather: {weather_info} ---\n"
    for activity in day_plan.get("activities", []):
        download_text += f"{activity['time_slot']}: {activity['activity']} (Cost: ${activity['cost']:.2f})\n"
    download_text += "\n"
logger.debug("Prepared plain text itinerary for download")

st.download_button(
    label="📄 Download Itinerary (Plain Text)",
    data=download_text,
    file_name=f"{destination}_itinerary.txt",
    mime="text/plain"
)
logger.info("✅ Download buttons rendered")