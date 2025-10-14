import os
import re
import streamlit as st
import sys
from datetime import datetime, timedelta

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

# Calculate integer duration for API call and LLM prompt (Robust fix for AttributeError)
duration_days = 3  # Default value
try:
    duration_days = int(str(duration).split()[0])
except (ValueError, IndexError, AttributeError):
    pass  # Use default if parsing fails

# --- ROBUST DATE PARSING BLOCK (Needed for API call) ---
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
    top_places = search_attractions(f"Best attractions in {destination}",destination, top_k=6)
    place_names = [p.get("name", "Unknown") for p in top_places]
    summary = ", ".join(place_names)
    st.success("✅ Attraction data fetched.")

# --- STEP 2: Fetch Forecast for Constraint Validation (NEW RAG Step) ---
with st.spinner("Step 2/3: Fetching multi-day weather forecast for planning..."):
    # Call the new function with the CORRECTED date format
    weather_report = get_forecast_summary(destination, start_date_str, duration_days)
    if "unavailable" in weather_report or "limit reached" in weather_report:
        st.warning(f"⚠️ Weather constraint validation limited: {weather_report}. Proceeding with best-effort planning.")
    else:
        st.success("✅ Multi-day weather forecast secured for constraint validation.")

# --- Compose the LLM prompt ---
system_prompt = f"""
You are an expert travel planner agent. Your goal is to create a detailed, constraint-aware, multi-day itinerary.

**STRICT CONSTRAINTS:**
1. **Budget:** Strictly adhere to the ${budget} limit.
2. **Duration:** Plan for exactly {duration_days} days.
3. **Weather-Based Validation (CRITICAL):** Use the provided **Weather Forecast** to actively validate and adjust activity types for **budget, time, and accessibility**.
    - If a day includes a **(HEAVY RAIN/SNOW WARNING)**: Favor low-cost, indoor, or covered activities. This ensures budget compliance (no money wasted on unusable outdoor events), saves time (by avoiding transportation delays), and aids accessibility (by avoiding slippery, uneven outdoor paths).
    - If conditions are clear: Favor outdoor sights and walking tours.
    - **Ensure your itinerary narrative explains how weather dictated activity choices for specific days.**

**DATA:**
- Destination: {destination}
- Travel Start Date: {start_date_str}
- Top Attractions (RAG Data): {summary}
- **Weather Forecast for Trip Period (Use this for validation and planning):**
{weather_report}

**FORMAT:**
The final response must be crisp and structured clearly like:
Day 1 – Morning / Afternoon / Evening.
Day 2 – Morning / Afternoon / Evening.
...
"""

# --- Call GPT model ---
client = OpenAI(api_key=OPENAI_API_KEY)
with st.spinner("✈️ Generating itinerary..."):
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": "Generate the personalized travel itinerary now."}]
    )

raw_plan = response.choices[0].message.content.strip()

# --- Clean text and structured display (CRITICAL FIX: Robust Parsing) ---
# 1. Aggressively clean up common LLM markdown before splitting
clean_plan = re.sub(r"[*#_`>]+", "", raw_plan).strip()

# 2. Split by day headings
# This regex captures the title and the content after it, ignoring the titles themselves in the main split
day_sections = re.split(r"(\bDay\s*\d+[^\n:]*)", clean_plan, flags=re.IGNORECASE)

# The first element is usually empty; we extract titles and content blocks
day_titles = day_sections[1::2]
plan_sections = day_sections[2::2]

if not day_titles:
    st.warning("Could not detect day sections clearly; displaying full text below.")
    st.markdown(raw_plan.replace("\n", "<br>"), unsafe_allow_html=True)
else:
    st.success("✅ Personalized itinerary ready!")

    st.markdown("### 🗓️ Your Smart Itinerary")

    for i, section in enumerate(plan_sections):
        if i >= len(day_titles):
            break

        title = day_titles[i].strip()
        # Clean title of emojis and extra space
        title = re.sub(r'[\s\n\r\t]+', ' ', title).strip()
        title = re.sub(r'🌅|☀️|🌆|🌙', '', title).strip()

        st.markdown(f"#### 🌅 {title}")

        with st.container():
            # NEW FIX: Aggressive cleaning of time labels inside the content before parsing.
            # This prevents stray emojis/words (like '☀️ Morning') from breaking the regex segmenter.
            section_cleaned = re.sub(r'(?:🌅|☀️|🌆|🌙)\s*(Morning|Afternoon|Evening)', '', section, flags=re.IGNORECASE)

            # 3. FIX: Use re.findall to reliably extract Time Label and the following Content
            time_blocks = re.findall(
                r'(Morning|Afternoon|Evening)(.*?)(?=Morning|Afternoon|Evening|$)',
                section_cleaned, # Use the cleaned section
                flags=re.IGNORECASE | re.DOTALL
            )

            if time_blocks:
                for time_label, details in time_blocks:
                    time_label = time_label.capitalize()

                    # Final cleanup of the details content
                    details = details.strip()
                    if details.startswith(':'):
                        details = details[1:].strip()

                    icon = "☀️" if "Morning" in time_label else ("🌆" if "Afternoon" in time_label else "🌙")
                    st.markdown(
                        f"<div style='background-color:#f9fafb;padding:15px;border-radius:10px;margin-bottom:10px;'>"
                        f"<b>{icon} {time_label}</b><br>{details.replace(chr(10), '<br>')}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(f"**Detailed plan content:**<br>{section.replace(chr(10), '<br>')}", unsafe_allow_html=True)
# Combine all plan sections for download
final_plan_text = "\n\n".join([day_titles[i] + section for i, section in enumerate(plan_sections)])

st.divider()

# --- Download option ---
st.download_button(
    label="📥 Download Itinerary",
    data=final_plan_text,
    file_name=f"{destination}_itinerary.txt",
    mime="text/plain"
)