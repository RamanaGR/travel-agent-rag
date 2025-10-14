import json
import os
import time
import requests
from datetime import datetime, timedelta, date as date_obj  # ADDED
from config.config import OPENWEATHER_KEY, OPENWEATHER_ENDPOINT

COUNTER_FILE = "data/api_usage_v3.txt"
CACHE_FILE = "data/weather_cache_v3.json"
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


# --- NEW HELPER FUNCTION TO GET COORDINATES ---
def _get_coordinates(city: str):
    """Fetches latitude and longitude for a city name using OWM Geocoding API."""
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_KEY}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data:
            return data[0]['lat'], data[0]['lon']
        return None, None
    except requests.exceptions.RequestException as e:
        return None, None
def get_forecast_summary_v2(city: str, start_date_str: str, duration_days: int) -> str:
    try:
        lat, lon = _get_coordinates(city)
        # 5-day / 3-hour forecast endpoint, requires lat/lon for best data
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_KEY}&units=metric"
        res = requests.get(url, timeout=5)
        # _increment_counter()

        if res.status_code != 200:
            return f"(Forecast fetch error {res.status_code})"

        data = res.json()
        if not data.get('list'):
            return "Detailed weather forecast unavailable."

        return data.get('list')
    except Exception as e:
        return f"(Forecast unavailable — {e})"

# --- NEW CORE FUNCTION: GET FORECAST SUMMARY ---
def get_forecast_summary(city: str, start_date_str: str, duration_days: int) -> str:
    """
    Fetches and summarizes the weather forecast for the trip duration (up to 5 days).
    This function uses the 5-day/3-hour forecast API and aggregates the data daily.
    """
    # 🚨 CRITICAL: Explicit check for the configuration key 🚨
    if not OPENWEATHER_KEY:
        return "Weather data unavailable: OPENWEATHER_KEY is missing or empty in config/config.py"
    # 🚨 END CRITICAL CHECK 🚨
    try:
        lat, lon = _get_coordinates(city)
    except Exception as e:
        return f"(coordinates unavailable — {e})"


    if lat is None or lon is None:
        return "Weather data unavailable: Could not find city coordinates."

    # cache = _load_cache()
    # cache_key = f"forecast_{city}_{start_date_str}_{duration_days}"
    # now = time.time()
    #
    # if cache and cache_key in cache and now - cache[cache_key]["timestamp"] < CACHE_TTL:
    #     return f"(cached forecast) {cache[cache_key]['data']}"
    #
    # counter = _load_counter()
    # if counter["count"] >= DAILY_LIMIT:
    #     return "⚠️ Daily API limit reached for forecast."

    try:
        # 5-day / 3-hour forecast endpoint, requires lat/lon for best data
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_KEY}&units=metric"
        res = requests.get(url, timeout=5)
        #_increment_counter()

        if res.status_code != 200:
            return f"(Forecast fetch error {res.status_code})"

        data = res.json()
        if not data.get('list'):
            return "Detailed weather forecast unavailable."

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = start_date + timedelta(days=duration_days - 1)

        daily_weather = {}

        for item in data['list']:
            forecast_dt = datetime.fromtimestamp(item['dt']).date()

            if start_date <= forecast_dt <= end_date:
                day_str = forecast_dt.strftime('%Y-%m-%d')

                if day_str not in daily_weather:
                    daily_weather[day_str] = {
                        'temps': [],
                        'descriptions': set(),
                        'rain_sum': 0  # Total rain for the day in mm
                    }

                daily_weather[day_str]['temps'].append(item['main']['temp'])
                daily_weather[day_str]['descriptions'].add(item['weather'][0]['description'])
                # Aggregate rain/snow volume
                if 'rain' in item and '3h' in item['rain']:
                    daily_weather[day_str]['rain_sum'] += item['rain']['3h']
                if 'snow' in item and '3h' in item['snow']:
                    daily_weather[day_str]['rain_sum'] += item['snow']['3h']  # Treat snow volume the same for planning

        weather_lines = []
        for i, (day_str, data) in enumerate(daily_weather.items()):
            avg_temp = sum(data['temps']) / len(data['temps']) if data['temps'] else 0
            main_desc = ", ".join(data['descriptions'])
            rain_alert = ""
            if data['rain_sum'] > 10:  # Heuristic for heavy rain/snow
                rain_alert = "** (HEAVY RAIN/SNOW WARNING - Plan INDOOR/COVERED activities)**"

            weather_lines.append(
                f"Day {i + 1} ({day_str}): Avg Temp {int(avg_temp)}°C. "
                f"Conditions: {main_desc.capitalize()}{rain_alert}. "
            )

        weather_summary = "\n".join(weather_lines)

        # cache[cache_key] = {"data": weather_summary, "timestamp": now}
        # _save_cache(cache)
        return weather_summary

    except Exception as e:
        return f"(Forecast unavailable — {e})"
