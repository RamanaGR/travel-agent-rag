import re
from modules.rag_engine import RAGEngine


def generate_itinerary(parsed, weather_func, attractions):
    location = parsed.get("location") or "Unknown"
    weather_info = weather_func(location)

    try:
        num_days = int(re.search(r"(\d+)", str(parsed.get("days") or "3")).group(1))
    except Exception:
        num_days = 3
    rag = RAGEngine()
    # Build FAISS index and search
    index, texts = rag.build_index(attractions)
    interest_query = f"top tourist attractions in {location}"
    recs = rag.search(index, texts, interest_query, top_k=3)

    plan = []
    for d in range(1, num_days + 1):
        plan.append({
            "day": d,
            "activities": [recs[d % len(recs)]] if recs else ["Explore local sights"]
        })

    itinerary = {
        "destination": location,
        "duration_days": num_days,
        "budget": parsed.get("budget") or "Not given",
        "current_weather": weather_info,
        "recommended_attractions": recs,
        "plan": plan
    }
    return itinerary
