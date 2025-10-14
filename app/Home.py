import os
import sys

import streamlit as st
# Add project root to sys.path (go up one directory from app/)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from modules.nlp_extractor import extract_entities

current_dir = os.path.dirname(os.path.abspath(__file__))  # Gets /app/ dir
css_path = os.path.join(current_dir, 'assets', 'style.css')  # Builds full path

# Load and inject CSS
with open(css_path, 'r') as f:
    css_content = f.read()

st.markdown(
    f"<style>{css_content}</style>",
    unsafe_allow_html=True
)
st.set_page_config(
    page_title="AI Travel Planner",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.sidebar.image("app/assets/img.png", use_container_width=True)
st.sidebar.markdown("### ✈️ AI Travel Planner")
st.sidebar.write("Personalized itineraries using Generative AI")
st.sidebar.markdown("---")
st.sidebar.subheader("🧭 Navigation")

st.sidebar.page_link("Home.py", label="🏠 Home")
st.sidebar.page_link("pages/1_Travel_Results.py", label="📍 Travel Results")
st.sidebar.page_link("pages/2_Itinerary_Generator.py", label="🧳 Itinerary Generator")

# --- Title ---
st.title("🌍 Plan Your Next Adventure with AI")
st.markdown("""
#### Your smart travel companion for creating personalized itineraries.
Just tell me your destination, duration, and budget — I’ll do the rest!
""")

st.divider()

# --- Input Section ---
st.markdown("### ✏️ Tell me about your trip")
user_query = st.text_input(
    "Example: *Plan a 4-day trip to Miami in December under $1000*"
)

col1, col2 = st.columns([1, 3])
with col1:
    generate = st.button("✨ Generate Plan")
with col2:
    st.caption("AI will extract details and prepare your plan instantly!")

if generate:
    if not user_query.strip():
        st.warning("Please enter a travel request first.")
    else:
        with st.spinner("Analyzing your request..."):
            details = extract_entities(user_query)
            st.write("🔍 Debug:", details)
            destination = details.get("destination")
            budget = details.get("budget")
            duration = details.get("duration")
            date = details.get("date")

            st.session_state.update({
                "query": user_query,
                "destination": destination,
                "budget": budget,
                "duration": duration,
                "date": date,
            })

        st.success(f"✅ Destination: **{destination}**, Budget: **${budget}**, Duration: **{duration} days**")
        st.page_link("pages/1_Travel_Results.py", label="➡️ View AI Travel Plan", icon="🧭")