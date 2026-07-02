import json
import logging
import os
import time
from datetime import datetime, timedelta

import requests

from config.config import (
    OPENWEATHER_ENDPOINT,
    OPENWEATHER_ENDPOINT_CORD,
    OPENWEATHER_KEY,
    WEATHER_CACHE_FILE,
    WEATHER_COUNTER_FILE,
)

logger = logging.getLogger(__name__)

CACHE_TTL = 3600
DAILY_LIMIT = 1000


def _load_counter():
    today = time.strftime("%Y-%m-%d")
    if not os.path.exists(WEATHER_COUNTER_FILE):
        return {"date": today, "count": 0}
    try:
        with open(WEATHER_COUNTER_FILE, "r") as f:
            data = json.load(f)
        if data.get("date") != today:
            data = {"date": today, "count": 0}
        return data
    except Exception as e:
        logger.error("Error loading API counter: %s", e)
        return {"date": today, "count": 0}


def _save_counter(data):
    os.makedirs(os.path.dirname(WEATHER_COUNTER_FILE), exist_ok=True)
    try:
        with open(WEATHER_COUNTER_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error("Error saving API counter: %s", e)


def _increment_counter():
    data = _load_counter()
    data["count"] += 1
    _save_counter(data)
    return data["count"]


def load_counter():
    return _load_counter()


def _load_cache():
    if os.path.exists(WEATHER_CACHE_FILE):
        try:
            with open(WEATHER_CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Error loading weather cache: %s", e)
            return {}
    return {}


def _save_cache(cache):
    os.makedirs(os.path.dirname(WEATHER_CACHE_FILE), exist_ok=True)
    try:
        with open(WEATHER_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception as e:
        logger.error("Error saving weather cache: %s", e)


def _get_coordinates(city: str):
    """Fetch latitude and longitude for a city using OpenWeatherMap geocoding."""
    url = f"{OPENWEATHER_ENDPOINT_CORD}?q={city}&limit=1&appid={OPENWEATHER_KEY}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data:
            return data[0]["lat"], data[0]["lon"]
    except requests.exceptions.RequestException as e:
        logger.error("Geocoding failed for %s: %s", city, e)
    return None, None


def get_weather(city: str) -> str:
    """Fetch current weather for a city with caching and rate limiting."""
    cache = _load_cache()
    now = time.time()
    cache_key = f"current:{city.lower()}"

    if cache_key in cache and now - cache[cache_key]["timestamp"] < CACHE_TTL:
        return f"(cached) {cache[cache_key]['data']}"

    counter = _load_counter()
    if counter["count"] >= DAILY_LIMIT:
        return "Daily API limit reached — using cached result if available."

    if not OPENWEATHER_KEY:
        return "Weather service unavailable (API key missing)."

    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={city}&appid={OPENWEATHER_KEY}&units=metric"
        )
        response = requests.get(url, timeout=5)
        _increment_counter()

        if response.status_code != 200:
            return f"Weather fetch error ({response.status_code})"

        result = response.json()
        desc = result["weather"][0]["description"]
        temp = result["main"]["temp"]
        feels = result["main"]["feels_like"]
        weather_text = f"{desc}, {temp}°C (feels {feels}°C)"

        cache[cache_key] = {"data": weather_text, "timestamp": now}
        _save_cache(cache)
        return weather_text
    except Exception as e:
        logger.error("Weather fetch failed for %s: %s", city, e)
        return f"Weather unavailable ({e})"


def get_forecast_summary(city_name, start_date_str, duration_days):
    """Fetch the 5-day forecast and return a summarized daily report."""
    lat, lon = _get_coordinates(city_name.strip())
    if lat is None or lon is None:
        return "Weather data unavailable: Could not find city coordinates."

    if not OPENWEATHER_KEY:
        logger.error("OPENWEATHER_KEY is missing.")
        return "Weather service unavailable (API key missing)."

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        logger.error("Invalid date format: %s", start_date_str)
        return "Weather service unavailable (invalid start date)."

    city = city_name.strip()
    if not city:
        return "Weather service unavailable (no city provided)."

    cache_key = f"{city.lower()}-{start_date_str}-{duration_days}"
    cache = _load_cache()
    now = time.time()

    if cache_key in cache and (now - cache[cache_key]["timestamp"]) < CACHE_TTL:
        logger.info("Cache hit for weather forecast: %s", city)
        return cache[cache_key]["data"]

    counter = _load_counter()
    if counter["count"] >= DAILY_LIMIT:
        logger.warning("Daily API limit reached: %s/%s", counter["count"], DAILY_LIMIT)
        return cache.get(cache_key, {}).get(
            "data", "Weather data is currently unavailable (API limit reached)."
        )

    try:
        url = f"{OPENWEATHER_ENDPOINT}?lat={lat}&lon={lon}&appid={OPENWEATHER_KEY}&units=metric"
        logger.info("Calling OpenWeatherMap forecast API for %s", city)
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            logger.error("OpenWeather API error: %s", response.status_code)
            return cache.get(cache_key, {}).get(
                "data", f"Weather forecast failed (status {response.status_code})."
            )

        _increment_counter()
        data = response.json()
    except requests.exceptions.Timeout:
        logger.error("OpenWeather API request timeout.")
        return cache.get(cache_key, {}).get("data", "Weather forecast failed (timeout).")
    except requests.exceptions.RequestException as e:
        logger.error("OpenWeather API network error: %s", e)
        return cache.get(cache_key, {}).get("data", "Weather forecast failed (network error).")
    except json.JSONDecodeError as e:
        logger.error("Failed to decode OpenWeather response: %s", e)
        return cache.get(cache_key, {}).get("data", "Weather forecast failed (invalid response).")

    forecast_list = data.get("list", [])
    if not forecast_list:
        return "Weather forecast is currently unavailable for this period."

    daily_weather = {}
    end_date = start_date + timedelta(days=duration_days - 1)
    for item in forecast_list:
        dt_obj = datetime.fromtimestamp(item["dt"]).date()
        if start_date <= dt_obj <= end_date:
            day_str = dt_obj.strftime("%Y-%m-%d")
            if day_str not in daily_weather:
                daily_weather[day_str] = {"temps": [], "descriptions": set(), "rain_sum": 0}

            daily_weather[day_str]["temps"].append(item["main"]["temp"])
            daily_weather[day_str]["descriptions"].add(item["weather"][0]["description"])
            if "rain" in item and "3h" in item["rain"]:
                daily_weather[day_str]["rain_sum"] += item["rain"]["3h"]
            if "snow" in item and "3h" in item["snow"]:
                daily_weather[day_str]["rain_sum"] += item["snow"]["3h"]

    weather_lines = []
    for i, day_str in enumerate(sorted(daily_weather.keys())):
        day_data = daily_weather[day_str]
        avg_temp = sum(day_data["temps"]) / len(day_data["temps"]) if day_data["temps"] else 0
        main_desc = ", ".join(day_data["descriptions"])
        rain_alert = ""
        if day_data["rain_sum"] > 10:
            rain_alert = " (HEAVY RAIN/SNOW WARNING - plan indoor/covered activities)"

        weather_lines.append(
            f"Day {i + 1} ({day_str}): Avg Temp {int(avg_temp)}°C. "
            f"Conditions: {main_desc.capitalize()}{rain_alert}."
        )

    weather_summary = "\n".join(weather_lines)
    cache[cache_key] = {"data": weather_summary, "timestamp": now}
    _save_cache(cache)
    return weather_summary


def parse_forecast_to_days(weather_report: str, duration_days: int) -> list[dict]:
    """Parse forecast summary text into structured day cards for the UI."""
    days = []
    if not weather_report:
        return [{"day": i + 1, "summary": "Unavailable", "temp": None, "rain_warning": False} for i in range(duration_days)]

    lines = [line.strip() for line in weather_report.split("\n") if line.strip()]
    for i in range(duration_days):
        day_tag = f"Day {i + 1}"
        line = next((ln for ln in lines if ln.startswith(day_tag)), None)
        if not line:
            days.append({"day": i + 1, "summary": "Details unavailable", "temp": None, "rain_warning": False})
            continue

        rain_warning = "RAIN" in line.upper() or "SNOW" in line.upper()
        temp = None
        if "Avg Temp" in line:
            try:
                temp = int(line.split("Avg Temp")[1].split("°C")[0].strip())
            except (ValueError, IndexError):
                temp = None

        summary = line.split(": ", 1)[-1] if ": " in line else line
        days.append({
            "day": i + 1,
            "summary": summary,
            "temp": temp,
            "rain_warning": rain_warning,
        })

    return days
