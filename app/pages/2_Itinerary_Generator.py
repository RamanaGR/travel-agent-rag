import os

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
Highlight must-see attractions ({summary}), local culture, weather tips, and dining suggestions.
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

plan = response.choices[0].message.content
st.success("✅ Personalized itinerary ready!")

# --- Display itinerary in styled container ---
st.markdown("### 🗓️ Your Smart Itinerary")
st.markdown(
    f"<div style='background-color:#f9fafb;padding:20px;border-radius:12px;'>"
    f"{plan.replace('\n', '<br>')}"
    f"</div>",
    unsafe_allow_html=True
)

# --- Download option ---
st.download_button(
    label="📥 Download Itinerary",
    data=plan,
    file_name=f"{destination}_itinerary.txt",
    mime="text/plain"
)
