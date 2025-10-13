import os
import re
import streamlit as st
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from openai import OpenAI
from modules.rag_engine import search_attractions
from config.config import OPENAI_API_KEY

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

# --- Verify context ---
if "destination" not in st.session_state:
    st.error("Please go to the Home page first.")
    st.stop()

destination = st.session_state["destination"]
budget = st.session_state["budget"]
duration = st.session_state["duration"]
date = st.session_state["date"]

st.markdown(f"# 🧳 AI-Generated Itinerary for {destination}")
st.write(f"💰 Budget: ${budget} | 🕓 Duration: {duration} days | 📅 Travel: {date}")
st.divider()

# --- Retrieve context data ---
with st.spinner("Gathering top attractions..."):
    top_places = search_attractions(f"Best attractions in {destination}", top_k=6)
    place_names = [p.get("name", "Unknown") for p in top_places]
    summary = ", ".join(place_names)

# --- Compose the LLM prompt ---
prompt = f"""
Plan a detailed {duration}-day travel itinerary for {destination} in {date}, under ${budget} budget.
Highlight must-see attractions ({summary}), local culture, weather tips, and dining suggestions. Response should be crisp and attractive.
Provide a structured plan like:
Day 1 – Morning / Afternoon / Evening.
"""

# --- Call GPT model ---
client = OpenAI(api_key=OPENAI_API_KEY)
with st.spinner("✈️ Generating itinerary..."):
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}]
    )

raw_plan = response.choices[0].message.content.strip()

# --- Clean text ---
plan = re.sub(r"[*#_`>]+", "", raw_plan).strip()

# --- Split by day headings for structured display ---
day_sections = re.split(r"\bDay\s*\d+", plan, flags=re.IGNORECASE)
day_titles = re.findall(r"\bDay\s*\d+[^\n:]*", plan, flags=re.IGNORECASE)

if not day_titles:
    st.warning("Could not detect day sections clearly; displaying full text below.")
    st.markdown(plan.replace("\n", "<br>"), unsafe_allow_html=True)
else:
    st.success("✅ Personalized itinerary ready!")

    st.markdown("### 🗓️ Your Smart Itinerary")

    for i, section in enumerate(day_sections[1:], start=1):
        title = day_titles[i - 1].strip()
        # Try to split into Morning / Afternoon / Evening
        parts = re.split(r"(Morning|Afternoon|Evening)", section, flags=re.IGNORECASE)
        st.markdown(f"#### 🌅 {title}")

        with st.container():
            for j in range(1, len(parts), 2):
                time_label = parts[j].capitalize()
                details = parts[j + 1].strip()
                icon = "☀️" if "Morning" in time_label else ("🌆" if "Afternoon" in time_label else "🌙")
                st.markdown(
                    f"<div style='background-color:#f9fafb;padding:15px;border-radius:10px;margin-bottom:10px;'>"
                    f"<b>{icon} {time_label}</b><br>{details.replace(chr(10), '<br>')}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

st.divider()

# --- Download option ---
st.download_button(
    label="📥 Download Itinerary",
    data=plan,
    file_name=f"{destination}_itinerary.txt",
    mime="text/plain"
)

# --- Download option ---
st.download_button(
    label="📥 Download Itinerary",
    data=plan,
    file_name=f"{destination}_itinerary.txt",
    mime="text/plain"
)
