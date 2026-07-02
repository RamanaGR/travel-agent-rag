import json
import logging
import os
import sys
from datetime import datetime, timedelta

import streamlit as st
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(project_root)

from app.components.layout import render_trip_summary_bar, setup_page
from config.config import OPENAI_API_KEY
from modules.rag_engine import retrieve_for_trip
from modules.retrieval import check_grounding, format_sources_for_prompt
from modules.weather_api import get_forecast_summary, parse_forecast_to_days

setup_page("AI Itinerary Generator", "🧳", "itinerary")

if "destination" not in st.session_state:
    st.error("Please start from the Home page.")
    st.stop()

destination = st.session_state["destination"]
budget = st.session_state["budget"]
duration = st.session_state["duration"]
date = st.session_state["date"]
user_query = st.session_state.get("query", "")
selected_attractions = st.session_state.get("selected_attractions", [])

try:
    duration_days = int(duration)
except (TypeError, ValueError):
    duration_days = 3 if not (isinstance(duration, str) and "week" in duration.lower()) else 5

try:
    start_date = datetime.strptime(date, "%Y-%m-%d").date()
except ValueError:
    start_date = datetime.now().date()
start_date_str = start_date.strftime("%Y-%m-%d")

st.title(f"{duration_days}-Day Itinerary for {destination}")
render_trip_summary_bar()
st.divider()

if not OPENAI_API_KEY:
    st.error("OpenAI API key is missing.")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

st.markdown("### Generate Your Itinerary")
st.caption("Click below to fetch weather, retrieve attractions, and generate your plan.")

if selected_attractions:
    st.info(f"{len(selected_attractions)} attractions selected from the preview page.")
else:
    st.warning("No attractions selected. Retrieval will use all indexed attractions.")

generate = st.button("Generate Itinerary", type="primary")

if generate:
    weather_report = st.session_state.get("weather_report")
    forecast_days = st.session_state.get("forecast_days")

    with st.status("Building your itinerary...", expanded=True) as status:
        if not weather_report:
            status.write("Fetching weather forecast...")
            weather_report = get_forecast_summary(destination, start_date_str, duration_days)
            forecast_days = parse_forecast_to_days(weather_report, duration_days)
            st.session_state.weather_report = weather_report
            st.session_state.forecast_days = forecast_days

        status.write("Retrieving attractions via hybrid RAG...")
        if st.session_state.get("rag_index_built"):
            top_places = retrieve_for_trip(
                user_query=user_query,
                destination=destination,
                budget=budget,
                duration=duration,
                date=date,
                top_k=8,
                selected_attractions=selected_attractions or None,
            )
        else:
            top_places = selected_attractions

        sources_text = format_sources_for_prompt(top_places)
        st.session_state.rag_sources = top_places

        status.write("Generating itinerary with GPT-4o...")
        system_prompt = f"""You are an expert travel agent creating detailed day-by-day itineraries.
Your response MUST be a single complete JSON object.

Trip details:
- DESTINATION: {destination}
- DURATION: {duration_days} days
- START DATE: {start_date_str}
- BUDGET: ${budget}
- WEATHER FORECAST: {weather_report}

Rules:
1. total_trip_spend MUST NOT exceed ${budget}.
2. itinerary array MUST contain exactly {duration_days} day objects.
3. Plan indoor/covered activities on rainy or snowy days.
4. You MUST prioritize activities from the numbered source list below.
5. When possible, use exact attraction names from the source list.

Numbered attraction sources (use these):
{sources_text}

JSON format:
{{
  "destination": "{destination}",
  "duration_days": {duration_days},
  "budget": {budget},
  "total_trip_spend": <float>,
  "notes": "<summary including weather and budget check>",
  "itinerary": [
    {{
      "day_title": "Day 1: <title>",
      "daily_spend": <float>,
      "date": "{start_date_str}",
      "activities": [
        {{"time_slot": "Morning", "activity": "<name and description>", "cost": <float>}},
        {{"time_slot": "Afternoon", "activity": "<name and description>", "cost": <float>}},
        {{"time_slot": "Evening", "activity": "<name and description>", "cost": <float>}}
      ]
    }}
  ]
}}"""

        user_prompt = (
            f"Generate a {duration_days}-day itinerary for {destination} "
            f"starting {start_date_str} with a ${budget} budget."
        )

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
            )
            itinerary_data = json.loads(response.choices[0].message.content)
            st.session_state.itinerary_data = itinerary_data
            st.session_state.itinerary_generated = True
            status.update(label="Itinerary generated!", state="complete")
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            st.error(f"Generation failed: {e}")
            st.stop()

if st.session_state.get("itinerary_data"):
    itinerary_data = st.session_state.itinerary_data
    top_places = st.session_state.get("rag_sources", [])
    total_trip_spend = float(itinerary_data.get("total_trip_spend", 0.0))

    spend_ratio = min(total_trip_spend / float(budget), 1.0) if budget else 0
    st.markdown("### Budget Usage")
    st.progress(spend_ratio, text=f"${total_trip_spend:.2f} of ${budget} used")

    grounding_warnings = check_grounding(itinerary_data, top_places)
    if grounding_warnings:
        st.warning(
            "Some activities may not match retrieved attractions: "
            + "; ".join(grounding_warnings[:3])
            + ("..." if len(grounding_warnings) > 3 else "")
        )

    with st.expander("Sources used (RAG retrieval)", expanded=False):
        if top_places:
            for i, src in enumerate(top_places, 1):
                st.markdown(
                    f"**{i}. {src.get('name', 'Unknown')}** — "
                    f"{src.get('category', 'N/A')} | "
                    f"Rating: {src.get('rating', 'N/A')} | "
                    f"{src.get('match_reason', '')}"
                )
                if src.get("link"):
                    st.caption(src["link"])
        else:
            st.write("No RAG sources available for this trip.")

    st.markdown("### Day-by-Day Plan")
    day_plans = itinerary_data.get("itinerary", [])
    forecast_days = st.session_state.get("forecast_days", [])

    for day_index, day_plan in enumerate(day_plans):
        day_date = start_date + timedelta(days=day_index)
        day_date_str = day_date.strftime("%B %d, %Y")
        weather_info = "Weather unavailable."
        if forecast_days and day_index < len(forecast_days):
            weather_info = forecast_days[day_index].get("summary", weather_info)

        with st.container(border=True):
            st.subheader(day_plan.get("day_title", f"Day {day_index + 1}"))
            st.markdown(
                f"**Date:** {day_date_str} | **Daily spend:** "
                f"${day_plan.get('daily_spend', 0.0):.2f} | **Weather:** {weather_info}"
            )
            for activity in day_plan.get("activities", []):
                slot = activity.get("time_slot", "Activity")
                icon = "☀️" if "Morning" in slot else ("🌆" if "Afternoon" in slot else "🌙")
                st.markdown(
                    f"**{icon} {slot}** — {activity.get('activity', '')} "
                    f"(${activity.get('cost', 0.0):.2f})"
                )

    st.markdown("### Summary")
    notes = itinerary_data.get("notes", "").replace("*", "")
    st.info(notes or "No additional notes.")

    download_json = json.dumps(itinerary_data, indent=2)
    st.download_button(
        "Download Itinerary (JSON)",
        data=download_json,
        file_name=f"{destination}_itinerary.json",
        mime="application/json",
    )

    download_text = (
        f"ITINERARY FOR {destination}\nBudget: ${budget}\nSpend: ${total_trip_spend:.2f}\n\n"
    )
    for day_index, day_plan in enumerate(day_plans):
        day_date = (start_date + timedelta(days=day_index)).strftime("%B %d, %Y")
        download_text += f"--- {day_plan.get('day_title', '')} ({day_date}) ---\n"
        for activity in day_plan.get("activities", []):
            download_text += (
                f"{activity.get('time_slot')}: {activity.get('activity')} "
                f"(${activity.get('cost', 0.0):.2f})\n"
            )
        download_text += "\n"

    st.download_button(
        "Download Itinerary (Plain Text)",
        data=download_text,
        file_name=f"{destination}_itinerary.txt",
        mime="text/plain",
    )

st.page_link("pages/1_Travel_Results.py", label="Back to Results")
