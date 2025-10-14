import os
import re
import streamlit as st
import sys
import json
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
    duration_days = int(str(duration).split()[0])
except (ValueError, IndexError, AttributeError):
    pass

# --- ROBUST DATE PARSING BLOCK ---
travel_date_raw = date
start_date_str = None
try:
    dt_obj = datetime.strptime(str(travel_date_raw), '%B %Y')
    start_date_str = dt_obj.strftime('%Y-%m-01')
    if start_date_str != str(travel_date_raw):
        st.info(f"💡 Travel date inferred from '{travel_date_raw}' to '{start_date_str}'.")
except Exception:
    start_date_str = str(travel_date_raw)
    try:
        datetime.strptime(start_date_str, '%Y-%m-%d')
    except Exception:
        today = datetime.now().date()
        start_date_str = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        st.warning(
            f"⚠️ Could not parse travel date '{travel_date_raw}'. Defaulting to tomorrow: {start_date_str} for forecast.")

st.markdown(f"# 🧳 AI-Generated Itinerary for {destination}")
st.write(f"💰 Budget: ${budget} | 🕓 Duration: {duration} | 📅 Travel: {date}")
st.divider()

# --- Retrieve context data ---
with st.spinner("Gathering top attractions..."):
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


# --- NEW: Helper function to parse the multi-day weather string (THE FIX) ---
def parse_weather_summary(weather_report):
    """Parses the multi-line weather report string into a dictionary {day_num: summary_text}."""
    daily_data = {}

    # NEW Regex: Captures "Day N" then skips until "Conditions:" and captures the rest.
    # Pattern: Captures Day 1, then date, then the rest of the line starting after the colon.
    # The weather_api_new.py output is: "Day N (YYYY-MM-DD): Avg Temp X°C. Conditions: ...
    pattern = r"Day\s*(\d+)\s*\((.*?)\):\s*(.*)"

    # Strip the heavy rain/snow warning markers for a cleaner display
    cleaned_report = weather_report.replace('** (HEAVY RAIN/SNOW WARNING - Plan INDOOR/COVERED activities)**',
                                            '').replace('Avg Temp', 'Avg Temp')
    st.write(cleaned_report)
    for match in re.finditer(pattern, cleaned_report):
        day_num = int(match.group(1))
        # Keep only the conditions/temp part, removing any surrounding whitespace
        summary_text = match.group(3).strip()
        daily_data[day_num] = summary_text
    return daily_data


weather_lookup = parse_weather_summary(weather_report)
st.write(weather_lookup)
# --- Compose the LLM prompt (JSON Schema Instruction) ---
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
                                "activity": {"type": "string",
                                             "description": "Name of the activity. Do NOT include asterisks."},
                                "details": {"type": "string",
                                            "description": "Brief description of activity, dinner, and weather considerations. Do NOT include asterisks."},
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
                  "description": "A final summary explaining how the budget and weather constraints were met. Do NOT include asterisks."}
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
You MUST return the itinerary as a single JSON object that conforms exactly to the following structure. Do not include any text outside the JSON block. Ensure all cost fields are simple numbers (no dollar signs or commas). DO NOT use asterisks (*) or any other markdown formatting inside the JSON strings.

**JSON SCHEMA:**
{json_schema_string}
"""

# --- Call GPT model (Simple JSON Request) ---
client = OpenAI(api_key=OPENAI_API_KEY)
with st.spinner("✈️ Generating itinerary..."):
    itinerary_data = {}
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": "Generate the personalized travel itinerary now."}],
            # Use the simple, widely supported JSON response format
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

# --- Structured Display using JSON Data ---

st.markdown("### 🗓️ Your Smart Itinerary")
total_trip_spend = 0

day_plans = itinerary_data.get("itinerary", [])
if not day_plans:
    st.warning("The AI returned no itinerary data.")
    st.stop()

for day_index, day_plan in enumerate(day_plans):
    day_num = day_index + 1
    day_title = day_plan.get("day_title", f"Day {day_num}")
    daily_spend = day_plan.get("daily_spend", 0)
    total_trip_spend += daily_spend

    # 1. Get and append weather details
    # FIX: The key for weather_lookup is now the day number (day_num)
    weather_info = weather_lookup.get(day_num, "Weather details unavailable.")

    # 2. Append weather info and ensure title is clean
    title_with_weather = f"🌅 {day_title} (Daily Spend: ${daily_spend:.2f}) | **{weather_info}**".replace('*', '')

    st.markdown(f"#### {title_with_weather}")

    activities = day_plan.get("activities", [])

    for activity in activities:
        time_slot = activity.get("time_slot", "Activity")
        activity_name = activity.get("activity", "Unknown Activity")
        details = activity.get("details", "")
        cost = activity.get("cost", 0)

        icon = ""
        style_color = "#3498db"  # Default Blue (Morning)

        if "Morning" in time_slot:
            icon = "☀️"
            style_color = "#3498db"
        elif "Afternoon" in time_slot:
            icon = "🌆"
            style_color = "#f39c12"  # Orange
        elif "Evening" in time_slot:
            icon = "🌙"
            style_color = "#9b59b6"  # Purple

        # The block now takes up the full container width for even size
        st.markdown(
            f"<div style='border-left: 5px solid {style_color}; padding: 15px; border-radius: 5px; margin-bottom: 10px; background-color: #fcfcfc; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);'>"
            f"<b><span style='color: {style_color}; font-size: 16px;'>{icon} {time_slot}</span></b><br>"
            f"<h5 style='margin-top: 5px; margin-bottom: 5px; font-weight: 700;'>{activity_name.replace('*', '')}</h5>"
            f"Cost: <span style='color: #27ae60; font-weight: bold; font-size: 14px;'>${cost:.2f}</span><br>"
            f"<small style='color: #555;'>{details.replace('*', '')}</small>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown("---")

# --- Final Summary and Download ---
st.markdown("### Trip Summary and Notes")

# Ensure total spend and notes are clean
notes = itinerary_data.get("notes", "No specific notes provided by the AI.").replace('*', '')

st.markdown(f"**Total Trip Spend:** **${total_trip_spend:.2f}** (Budget: ${budget})")
st.info(notes)

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
    # Add weather to the text download
    day_num = day_plans.index(day_plan) + 1
    weather_info = weather_lookup.get(day_num, "Weather details unavailable.")

    download_text += f"--- {day_plan['day_title']} (Total: ${day_plan['daily_spend']:.2f}) | Weather: {weather_info} ---\n"
    for activity in day_plan.get("activities", []):
        download_text += f"{activity['time_slot']}: {activity['activity']} (Cost: ${activity['cost']:.2f})\n"
        download_text += f"  Details: {activity['details']}\n"
    download_text += "\n"
download_text += f"\nNOTES:\n{notes}"

st.download_button(
    label="📥 Download Itinerary (Text)",
    data=download_text,
    file_name=f"{destination}_itinerary.txt",
    mime="text/plain"
)