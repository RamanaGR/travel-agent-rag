from modules.parser import parse_user_query
from modules.weather_api import get_weather, load_counter
from modules.attractions_api import fetch_attractions, get_cached_attractions
from modules.itinerary_generator import generate_itinerary
import json, os

if __name__ == "__main__":
    q = input("Enter your travel request: ")
    parsed = parse_user_query(q)
    city = parsed.get("location")

    # fetch attractions (uses cache automatically)
    attractions = get_cached_attractions(city)
    if not attractions:
        attractions = fetch_attractions(city)

    itinerary = generate_itinerary(parsed, get_weather, attractions)
    print(json.dumps(itinerary, indent=4))

    usage = load_counter()
    print(f"\n📊 API Calls Today: {usage['count']}/1000")
