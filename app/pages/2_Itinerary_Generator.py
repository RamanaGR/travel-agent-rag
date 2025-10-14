import os
import re
import streamlit as st
import sys
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

# --- Compose the LLM prompt (FIX: Simplified, Prescriptive Format) ---
system_prompt = f"""
You are an expert travel planner agent. Your goal is to create a detailed, constraint-aware, multi-day itinerary.

**STRICT CONSTRAINTS:**
1. **Budget:** Strictly adhere to the ${budget} limit.
2. **Duration:** Plan for exactly {duration_days} days.
3. **Weather-Based Validation (CRITICAL):** Use the provided **Weather Forecast** to actively validate and adjust activity types. Explain how weather dictated activity choices in the narrative.

**DATA:**
- Destination: {destination}
- Travel Start Date: {start_date_str}
- Top Attractions (RAG Data): {summary}
- **Weather Forecast for Trip Period (Use this for validation and planning):**
{weather_report}

**FORMAT (CRITICAL):**
The final response **MUST** be structured EXACTLY as follows. Do not include any extra headings, introductory text, or concluding text, except for the required elements.

###
🌅 Day N (Date)
☀️ Morning
- Activity: [Activity Name]
- Details: [Brief description of activity and weather considerations.]
- **Cost: $[Numeric Value]**
🌆 Afternoon
- Activity: [Activity Name]
- Details: [Brief description of activity and weather considerations.]
- **Cost: $[Numeric Value]**
🌙 Evening
- Activity: [Activity Name]
- Details: [Brief description of activity and weather considerations and dinner.]
- **Cost: $[Numeric Value]**
**Day's Total Spend: $[Numeric Value]**

Repeat the entire block for each day, separated by '###'. Conclude with a final 'Total Trip Spend' line.
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

# --- Clean text and structured display (FIX: Hardened Parsing) ---
# 1. Aggressively clean up common LLM markdown before splitting
clean_plan = re.sub(r"[*#_`>]+", "", raw_plan).strip()

# FIX: Remove extra LLM noise lines before parsing, specifically the "Day Total Cost" line
clean_plan = re.sub(r'Day\s*\d+\s*Total\s*Cost.*', '', clean_plan, flags=re.IGNORECASE)
clean_plan = re.sub(r'Total Trip Spend.*', '', clean_plan, flags=re.IGNORECASE)

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
        title = re.sub(r'🌅|☀️|🌆|🌙|###', '', title).strip()

        st.markdown(f"#### 🌅 {title}")

        with st.container():
            # NEW FIX: Aggressive cleaning of stray time labels inside the content before parsing.
            section_cleaned = re.sub(r'(?:🌅|☀️|🌆|🌙)\s*(Morning|Afternoon|Evening)', '', section, flags=re.IGNORECASE)

            # 3. Use re.findall to reliably extract Time Label and the following Content
            # Regex: finds (Morning|Afternoon|Evening) followed by any content (.*?)
            # until the next time block or the end of the section ($)
            time_blocks = re.findall(
                r'(Morning|Afternoon|Evening)(.*?)(?=Morning|Afternoon|Evening|$)',
                section_cleaned,
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
# Re-extracting the total spend at the very end
total_spend_match = re.search(r'Total Trip Spend:\s*\$?([\d,]+)', raw_plan, re.IGNORECASE)
total_spend_line = ""
if total_spend_match:
    total_spend_line = f"\n\n**Total Trip Spend: ${total_spend_match.group(1)}**"

final_plan_text = "\n\n".join([day_titles[i] + section for i, section in enumerate(plan_sections)]) + total_spend_line

st.divider()

# --- Download option ---
st.download_button(
    label="📥 Download Itinerary",
    data=final_plan_text,
    file_name=f"{destination}_itinerary.txt",
    mime="text/plain"
)