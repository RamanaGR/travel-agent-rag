"""
travel_agent_main.py
Main agent orchestrator for personalized travel itinerary generation.
"""

import os
from modules.nlp_extractor import extract_entities
from modules.weather_api import get_weather
from modules.attractions_api import get_geo_id, fetch_attractions
from modules.rag_engine import RAGEngine


# ===============================================================
# CONFIGURATION
# ===============================================================
USE_OFFLINE_MODE = os.getenv("USE_OFFLINE_MODE", "False").lower() == "true"
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

# Initialize RAG Engine
rag = RAGEngine()


# ===============================================================
# HELPER
# ===============================================================
def format_itinerary(city, weather, attractions, budget, duration_days):
    """Generate a friendly, readable itinerary summary."""
    lines = []
    lines.append(f"🧭 Personalized Itinerary for {city}")
    lines.append("=" * (len(lines[-1]) + 2))
    if weather:
        lines.append(f"🌤 Weather: {weather})")
    if budget:
        lines.append(f"💰 Budget: around ${budget}")
    if duration_days:
        lines.append(f"📅 Duration: {duration_days} days")
    lines.append("\n📍 Top Recommended Attractions:\n")

    for i, att in enumerate(attractions[:5], 1):
        lines.append(f"{i}. {att['name']} - {att.get('category', 'General')} | ⭐ {att.get('rating', 'N/A')} ({att.get('reviews', 'N/A')} reviews)")
        if att.get('link'):
            lines.append(f"   🔗 {att['link']}")

    return "\n".join(lines)


# ===============================================================
# MAIN AGENT WORKFLOW
# ===============================================================
def run_travel_agent():
    print("🤖 Welcome to your AI Travel Planner!")
    user_input = input("Enter your travel request (e.g. 'Plan a 4-day trip to Miami in December under $1000'): ")

    # 1️⃣ Extract entities
    info = extract_entities(user_input)
    city = info["destination"]
    if not city:
        print("⚠️ Couldn’t detect a destination. Please mention a city.")
        return

    print(f"📍 Destination detected: {city}")
    print(f"💰 Budget: {info['budget'] or 'Not specified'}")
    print(f"📅 Duration: {info['duration_days'] or 'Not specified'} days")
    print(f"🗓 Dates: {info['start_date']} → {info['end_date']}")

    # 2️⃣ Fetch weather
    weather = None
    if not USE_OFFLINE_MODE:
        try:
            weather = get_weather(city)
            print(f"🌤 Weather fetched for {city}")
        except Exception as e:
            print(f"⚠️ Weather error: {e}")

    # 3️⃣ Fetch attractions (with geoId)
    geo_id = get_geo_id(city)
    if not geo_id:
        print(f"⚠️ Could not find geoId for {city}. Using cached data if available.")
    attractions = fetch_attractions(city, geo_id)

    if not attractions:
        print("⚠️ No attractions found. Please try another city.")
        return

    # 4️⃣ Use RAG to rank/summarize
    query = f"Top attractions and experiences for a {info['duration_days'] or 'few'} day trip to {city}"
    ranked_attractions = rag.search(query, top_k=5)

    # Merge top results with metadata
    combined = ranked_attractions or attractions

    # 5️⃣ Generate itinerary text
    itinerary = format_itinerary(city, weather, combined, info["budget"], info["duration_days"])
    print("\n" + itinerary)


# ===============================================================
# ENTRY POINT
# ===============================================================
if __name__ == "__main__":
    run_travel_agent()
