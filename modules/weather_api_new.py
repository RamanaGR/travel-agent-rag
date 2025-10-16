import json
import os
import time
import requests
from datetime import datetime, timedelta, date as date_obj
import logging

from config.config import OPENWEATHER_KEY, OPENWEATHER_ENDPOINT, OPENWEATHER_ENDPOINT_CORD

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

COUNTER_FILE = "data/api_usage_v3.txt"
CACHE_FILE = "data/weather_cache_v3.json"
CACHE_TTL = 3600  # 1 hour
DAILY_LIMIT = 1000

def _load_counter():
    today = time.strftime("%Y-%m-%d")
    if not os.path.exists(COUNTER_FILE):
        return {"date": today, "count": 0}
    try:
        with open(COUNTER_FILE, "r") as f:
            data = json.load(f)
        if data.get("date") != today:
            data = {"date": today, "count": 0}
        return data
    except Exception as e:
        logger.error(f"Error loading API counter: {e}")
        return {"date": today, "count": 0}

def _save_counter(data):
    os.makedirs(os.path.dirname(COUNTER_FILE), exist_ok=True)
    try:
        with open(COUNTER_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error saving API counter: {e}")

def _increment_counter():
    data = _load_counter()
    data["count"] += 1
    _save_counter(data)
    return data["count"]

def load_counter():
    return _load_counter()

def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading weather cache: {e}")
            return {}
    return {}

def _save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception as e:
        logger.error(f"Error saving weather cache: {e}")

def _get_coordinates(city: str):
    """Fetches latitude and longitude for a city name using OWM Geocoding API."""
    url = f"{OPENWEATHER_ENDPOINT_CORD}?q={city}&limit=1&appid={OPENWEATHER_KEY}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data:
            return data[0]['lat'], data[0]['lon']
        return None, None
    except requests.exceptions.RequestException as e:
        return None, None

def get_forecast_summary(city_name, start_date_str, duration_days):
    """
    Fetches the 5-day / 3-hour forecast and generates a summarized daily report.
    """

    lat, lon = _get_coordinates(city_name.strip())

    if lat is None or lon is None:
        return "Weather data unavailable: Could not find city coordinates."

    if not OPENWEATHER_KEY:
        logger.error("🚫 OPENWEATHER_KEY is missing. Check config/config.py or environment variables.")
        return "Weather service unavailable (API Key missing)."

    # Input validation and date parsing
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    except ValueError:
        logger.error(f"Invalid date format: {start_date_str}")
        return "Weather service unavailable (Invalid start date)."

    city = city_name.strip()
    if not city:
        logger.warning("City name is empty. Skipping weather fetch.")
        return "Weather service unavailable (No city provided)."

    # Cache key generation
    cache_key = f"{city.lower()}-{start_date_str}-{duration_days}"
    cache = _load_cache()
    now = time.time()

    # Check cache
    if cache_key in cache and (now - cache[cache_key]["timestamp"]) < CACHE_TTL:
        logger.info(f"✅ Cache hit for weather forecast: {city}")
        return cache[cache_key]["data"]

    # Check daily usage limit
    counter = _load_counter()
    if counter["count"] >= DAILY_LIMIT:
        logger.warning(f"🛑 Daily API limit reached: {counter['count']}/{DAILY_LIMIT}. Returning cached data or error.")
        return cache.get(cache_key, {}).get("data", "Weather data is currently unavailable (API limit reached).")

    # --- Execute API Call ---
    try:
        # 5-day / 3-hour forecast endpoint, requires lat/lon for best data
        url = f"{OPENWEATHER_ENDPOINT}?lat={lat}&lon={lon}&appid={OPENWEATHER_KEY}&units=metric"
        logger.debug(f"API Request URL: {url}")

        logger.info(f"⚡ Calling OpenWeatherMap API for {lat} and {lon} (Call #{counter['count'] + 1})...")
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            logger.error(f"❌ OpenWeather API Error: Status Code {response.status_code}. Response: {response.text}")
            return cache.get(cache_key, {}).get("data", f"Weather forecast failed (Status {response.status_code}).")

        # Increment counter on successful call
        _increment_counter()

        data = response.json()
        logger.info(f"API call successful. Data received for {data.get('city', {}).get('name', 'N/A')}.")

    except requests.exceptions.Timeout:
        logger.error("❌ OpenWeather API Request Timeout (10 seconds).")
        return cache.get(cache_key, {}).get("data", "Weather forecast failed (Request timeout).")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ OpenWeather API Network Error: {e}")
        return cache.get(cache_key, {}).get("data", "Weather forecast failed (Network error).")
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to decode JSON response from OpenWeather API: {e}")
        return cache.get(cache_key, {}).get("data", "Weather forecast failed (Invalid response format).")

    # --- Data Processing and Summarization ---

    forecast_list = data.get('list', [])
    if not forecast_list:
        logger.warning(f"No forecast data ('list') found in API response for {city}.")
        return "Weather forecast is currently unavailable for this period."

    daily_weather = {}

    # Determine the end date of the trip for filtering
    end_date = start_date + timedelta(days=duration_days - 1)
    for item in forecast_list:
        dt_obj = datetime.fromtimestamp(item['dt']).date()
        # Only process items within the trip duration
        if start_date <= dt_obj <= end_date:
            day_str = dt_obj.strftime('%Y-%m-%d')

            if day_str not in daily_weather:
                daily_weather[day_str] = {
                    'temps': [],
                    'descriptions': set(),
                    'rain_sum': 0
                }

            daily_weather[day_str]['temps'].append(item['main']['temp'])
            daily_weather[day_str]['descriptions'].add(item['weather'][0]['description'])
            if 'rain' in item and '3h' in item['rain']:
                daily_weather[day_str]['rain_sum'] += item['rain']['3h']
            if 'snow' in item and '3h' in item['snow']:
                daily_weather[day_str]['rain_sum'] += item['snow']['3h']

    weather_lines = []
    sorted_days = sorted(daily_weather.keys())
    for i, day_str in enumerate(sorted_days):
        data = daily_weather[day_str]
        avg_temp = sum(data['temps']) / len(data['temps']) if data['temps'] else 0
        main_desc = ", ".join(data['descriptions'])
        rain_alert = ""

        if data['rain_sum'] > 10:
            rain_alert = "** (HEAVY RAIN/SNOW WARNING - Plan INDOOR/COVERED activities)**"

        weather_lines.append(
            f"Day {i + 1} ({day_str}): Avg Temp {int(avg_temp)}°C. "
            f"Conditions: {main_desc.capitalize()}{rain_alert}. "
        )

    weather_summary = "\n".join(weather_lines)
    logger.info(f"Weather summary generated successfully for {len(sorted_days)} days.")

    # Save to cache before returning
    cache[cache_key] = {"data": weather_summary, "timestamp": now}
    _save_cache(cache)

    return weather_summary

if __name__ == "__main__":
    test_city = "London"
    test_start_date = date_obj.today().strftime('%Y-%m-%d')
    test_duration = 3

    print(f"--- Running Test Forecast for {test_city} ---")
    summary = get_forecast_summary(test_city, test_start_date, test_duration)
    print("\n[Generated Summary]")
    print(summary)
    print("-----------------------------------------")