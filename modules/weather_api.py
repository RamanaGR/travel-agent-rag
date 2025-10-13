import json
import os
import time
import requests
from config.config import OPENWEATHER_API_KEY, OPENWEATHER_ENDPOINT

COUNTER_FILE = "data/api_usage.txt"
CACHE_FILE = "data/weather_cache.json"
CACHE_TTL = 3600  # 1 hour
DAILY_LIMIT = 1000

def _load_counter():
    today = time.strftime("%Y-%m-%d")
    if not os.path.exists(COUNTER_FILE):
        return {"date": today, "count": 0}
    with open(COUNTER_FILE, "r") as f:
        data = json.load(f)
    if data.get("date") != today:
        data = {"date": today, "count": 0}
    return data

def _save_counter(data):
    os.makedirs(os.path.dirname(COUNTER_FILE), exist_ok=True)
    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f)

def _increment_counter():
    data = _load_counter()
    data["count"] += 1
    _save_counter(data)
    return data["count"]

def load_counter():
    return _load_counter()

def _load_cache():
    if os.path.exists(CACHE_FILE):
        return json.load(open(CACHE_FILE))
    return {}

def _save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    json.dump(cache, open(CACHE_FILE, "w"))

def get_weather(city: str) -> str:
    """Fetches live weather with caching and API call counting."""
    cache = _load_cache()
    now = time.time()

    # 1️⃣ Use cache if valid
    if city in cache and now - cache[city]["timestamp"] < CACHE_TTL:
        return f"(cached) {cache[city]['data']}"

    # 2️⃣ Check daily limit
    counter = _load_counter()
    if counter["count"] >= DAILY_LIMIT:
        return "⚠️ Daily API limit reached — using cached result if available."

    # 3️⃣ Make API call
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
        res = requests.get(url, timeout=5)
        _increment_counter()

        if res.status_code != 200:
            return f"(Weather fetch error {res.status_code})"

        result = res.json()
        desc = result["weather"][0]["description"]
        temp = result["main"]["temp"]
        feels = result["main"]["feels_like"]
        weather_text = f"{desc}, {temp}°C (feels {feels}°C)"

        # Save to cache
        cache[city] = {"data": weather_text, "timestamp": now}
        _save_cache(cache)
        return weather_text
    except Exception as e:
        return f"(Weather unavailable — {e})"
