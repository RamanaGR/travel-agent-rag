import os
import re
import streamlit as st
import sys
import json  # <-- Import for JSON parsing
from datetime import datetime, timedelta

# Append project root path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from openai import OpenAI
from modules.rag_engine import search_attractions
from config.config import OPENAI_API_KEY
from modules.weather_api_new import get_forecast_summary

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
css_path = os.path.join(project_root, 'assets', 'style.css')

# Load and inject CSS
with open(css_path, 'r') as f:
    css_content = f.read()

st.markdown(
    f"<style>{css_content}</style>",
    unsafe_allow_html=True
)

st.set_page_config(page_title="AI Itinerary Generator", page_icon="🧳", layout="wide")
st.sidebar.subheader("Navigation")
st.sidebar.page_link("Home.py", label="🏠 Home")
# --- Verify context ---
if "destination" not in st.session_state:
    st.error("Please go to the Home page first.")
    st.stop()

destination = st.session_state["destination"]
budget = st.session_state["budget"]
duration = st.session_state["duration"]
date = st.session_state["date"]

# Calculate integer duration for API call and LLM prompt
duration_days = 3  # Default value
try:
    # Robust way to extract the number from a string like "4 days"
    duration_days = int(str(duration).split()[0])
except (ValueError, IndexError, AttributeError):
    pass

# --- ROBUST DATE PARSING BLOCK ---
travel_date_raw = date
start_date_str = None
try:
    # Attempt to parse as 'Month YYYY'
    dt_obj = datetime.strptime(str(travel_date_raw), '%B %Y')
    start_date_str = dt_obj.strftime('%Y-%m-01')
    if start_date_str != str(travel_date_raw):
        st.info(f"💡 Travel date inferred from '{travel_date_raw}' to '{start_date_str}'.")
except Exception:
    start_date_str = str(travel_date_raw)
    try:
        # Check if it's already in YYYY-MM-DD format
        datetime.strptime(start_date_str, '%Y-%m-%d')
    except Exception:
        # Final fallback: use tomorrow's date
        today = datetime.now().date()
        start_date_str = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        st.warning(
            f"⚠️ Could not parse travel date '{travel_date_raw}'. Defaulting to tomorrow: {start_date_str} for forecast.")

st.markdown(f"# 🧳 AI-Generated Itinerary for {destination}")
st.write(f"💰 Budget: ${budget} | 🕓 Duration: {duration} | 📅 Travel: {date}")
st.divider()

# --- Retrieve context data ---
with st.spinner("Gathering top attractions..."):
    # Ensure correct signature is used: search_attractions(query, destination_city, top_k)
    top_places = search_attractions(f"Best attractions in {destination}", destination, top_k=6)
    place_names = [p.get("name", "Unknown") for p in top_places]
    summary = ", ".join(place_names)
    st.success("✅ Attraction data fetched.")

# --- STEP 2: Fetch Forecast for Constraint Validation ---
with st.spinner("Step 2/3: Fetching multi-day weather forecast for planning..."):
    weather_report = get_forecast_summary(destination, start_date_str, duration_days)
    if "unavailable" in weather_report or "limit reached" in weather_report:
        st.warning(f"⚠️ Weather constraint validation limited: {weather_report}. Proceeding with best-effort planning.")
    else:
        st.success("✅ Multi-day weather forecast secured for constraint validation.")

# --- Compose the LLM prompt (FIX: JSON Schema Instruction) ---
json_schema = {
    "type": "object",
    "properties": {
        "itinerary": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "day_title": {"type": "string", "description": "e.g., Day 1 (2025-12-01)"},
                    "daily_spend": {"type": "number", "description": "Total spend for this day."},
                    "activities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "time_slot": {"type": "string", "enum": ["Morning", "Afternoon", "Evening"]},
                                "activity": {"type": "string", "description": "Name of the activity."},
                                "details": {"type": "string",
                                            "description": "Brief description of activity, dinner, and weather considerations."},
                                "cost": {"type": "number", "description": "Estimated cost for this activity/meal."}
                            },
                            "required": ["time_slot", "activity", "details", "cost"]
                        }
                    }
                },
                "required": ["day_title", "daily_spend", "activities"]
            }
        },
        "notes": {"type": "string",
                  "description": "A final summary explaining how the budget and weather constraints were met."}
    },
    "required": ["itinerary", "notes"]
}

# Convert the schema to a string to place it into the SYSTEM PROMPT
json_schema_string = json.dumps(json_schema, indent=2)

system_prompt = f"""
You are an expert travel planner agent. Your goal is to create a detailed, constraint-aware, multi-day itinerary.

**STRICT CONSTRAINTS:**
1. **Budget:** The total trip spend must strictly adhere to the ${budget} limit.
2. **Duration:** Plan for exactly {duration_days} days.
3. **Weather-Based Validation (CRITICAL):** Use the provided **Weather Forecast** to actively validate and adjust activity types (e.g., prioritize indoor/covered activities on rainy days).

**DATA:**
- Destination: {destination}
- Travel Start Date: {start_date_str}
- Top Attractions (RAG Data): {summary}
- **Weather Forecast for Trip Period (Use this for validation and planning):**
{weather_report}

**FORMAT (CRITICAL):**
You MUST return the itinerary as a single JSON object that conforms exactly to the following structure. Do not include any text outside the JSON block. Ensure all cost fields are simple numbers (no dollar signs or commas).

**JSON SCHEMA:**
{json_schema_string}
"""

# --- Call GPT model (FIXED: Simple JSON Request) ---
client = OpenAI(api_key=OPENAI_API_KEY)
with st.spinner("✈️ Generating itinerary..."):
    itinerary_data = {}
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": "Generate the personalized travel itinerary now."}],
            # FIX: Use the simple, widely supported JSON response format
            response_format={"type": "json_object"}
        )
        raw_json_string = response.choices[0].message.content.strip()
        itinerary_data = json.loads(raw_json_string)
        st.success("✅ Personalized itinerary data received.")
    except json.JSONDecodeError:
        st.error("❌ Failed to decode JSON response from AI. Displaying raw text for debugging.")
        st.text(raw_json_string)
        st.stop()
    except Exception as e:
        # Catch any other API error
        st.error(f"❌ An error occurred during AI generation: {e}")
        st.stop()

# --- Structured Display using JSON Data (NEW UI CODE) ---

st.markdown("### 🗓️ Your Smart Itinerary")
total_trip_spend = 0

# Use columns for a visually appealing, structured display
day_plans = itinerary_data.get("itinerary", [])
if not day_plans:
    st.warning("The AI returned no itinerary data.")
    st.stop()

for day_plan in day_plans:
    day_title = day_plan.get("day_title", "Day N")
    daily_spend = day_plan.get("daily_spend", 0)
    total_trip_spend += daily_spend

    st.markdown(f"#### 🌅 {day_title} (Daily Spend: ${daily_spend:.2f})")

    # Use a maximum of 3 columns for Morning/Afternoon/Evening
    cols = st.columns(3)

    activities = day_plan.get("activities", [])

    # Ensure there are at most 3 activities per day for the column layout
    for i in range(min(3, len(activities))):
        activity = activities[i]
        time_slot = activity.get("time_slot", "Activity")
        activity_name = activity.get("activity", "Unknown Activity")
        details = activity.get("details", "")
        cost = activity.get("cost", 0)

        col = cols[i % 3]

        icon = ""
        if "Morning" in time_slot:
            icon = "☀️"
        elif "Afternoon" in time_slot:
            icon = "🌆"
        elif "Evening" in time_slot:
            icon = "🌙"

        with col:
            st.markdown(
                f"<div style='background-color:#f9fafb;padding:15px;border-radius:10px;min-height:200px;'>"
                f"<b>{icon} {time_slot}</b><br><br>"
                f"**{activity_name}**<br>"
                f"Cost: **${cost:.2f}**<br>"
                f"<small>{details}</small>"
                f"</div>",
                unsafe_allow_html=True,
            )
    st.markdown("---")

# --- Final Summary and Download ---
st.markdown("### Trip Summary and Notes")
st.markdown(f"**Total Trip Spend:** **${total_trip_spend:.2f}** (Budget: ${budget})")
st.info(itinerary_data.get("notes", "No specific notes provided by the AI."))

st.divider()

# Convert the JSON to a pretty-printed string for download
download_json = json.dumps(itinerary_data, indent=2)

st.download_button(
    label="📥 Download Itinerary (JSON)",
    data=download_json,
    file_name=f"{destination}_itinerary.json",
    mime="application/json"
)

# Optional: Download as plain text for easy reading
download_text = f"ITINERARY FOR {destination}\nTotal Budget: ${budget}\nTotal Spend: ${total_trip_spend:.2f}\n\n"
for day_plan in itinerary_data.get("itinerary", []):
    download_text += f"--- {day_plan['day_title']} (Total: ${day_plan['daily_spend']:.2f}) ---\n"
    for activity in day_plan.get("activities", []):
        download_text += f"{activity['time_slot']}: {activity['activity']} (Cost: ${activity['cost']:.2f})\n"
        download_text += f"  Details: {activity['details']}\n"
    download_text += "\n"
download_text += f"\nNOTES:\n{itinerary_data.get('notes', 'N/A')}"

st.download_button(
    label="📥 Download Itinerary (Text)",
    data=download_text,
    file_name=f"{destination}_itinerary.txt",
    mime="text/plain"
)