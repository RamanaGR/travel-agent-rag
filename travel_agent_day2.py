import requests
import json
import os
from datetime import datetime, timedelta, date as date_obj

# --- ⚠️ CONFIGURATION: REPLACE THIS PLACEHOLDER ⚠️ ---
# You need to manually replace this with your actual OpenWeatherMap API Key
# In your final project, this should come from config.config
OPENWEATHER_KEY = "lkj"


# -----------------------------------------------------

# --- HELPER FUNCTION TO GET COORDINATES (Requires API Key) ---
def _get_coordinates(city: str):
    """Fetches latitude and longitude for a city name using OWM Geocoding API."""
    if OPENWEATHER_KEY == "YOUR_OPENWEATHER_KEY":
        return None, None

    url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_KEY}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data:
            # Returns latitude and longitude
            return data[0]['lat'], data[0]['lon']
        return None, None
    except requests.exceptions.RequestException as e:
        print(f"Geocoding Error: {e}")
        return None, None


# --- CORE FUNCTION: GET FORECAST SUMMARY (with robust parsing) ---
def get_forecast_summary(city: str, start_date_str: str, duration_days: int) -> str:
    """
    Fetches and summarizes the weather forecast for the trip duration (up to 5 days).
    Uses robust JSON parsing to handle optional 'rain'/'snow' fields.
    """
    if OPENWEATHER_KEY == "YOUR_OPENWEATHER_KEY":
        return "Weather data unavailable: API key not set in the script."

    lat, lon = _get_coordinates(city)

    if lat is None or lon is None:
        return "Weather data unavailable: Could not find city coordinates."

    try:
        # Date setup for filtering the forecast data
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = start_date + timedelta(days=duration_days - 1)

        # API Call
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_KEY}&units=metric"
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        data = res.json()

        if not data.get('list'):
            return "Detailed weather forecast unavailable."

        daily_weather = {}

        # Iterate through the 3-hourly forecast items (the 'list' array)
        for item in data['list']:
            # Convert Unix timestamp to a Python date object
            forecast_dt = datetime.fromtimestamp(item['dt']).date()

            # Filter entries within the trip duration
            if start_date <= forecast_dt <= end_date:
                day_str = forecast_dt.strftime('%Y-%m-%d')

                # Initialize daily entry if not present
                if day_str not in daily_weather:
                    daily_weather[day_str] = {
                        'temps': [],
                        'descriptions': set(),
                        'rain_sum': 0  # Total precipitation for the day in mm
                    }

                # 1. Aggregate Temperature and Description
                daily_weather[day_str]['temps'].append(item['main']['temp'])
                daily_weather[day_str]['descriptions'].add(item['weather'][0]['description'])

                # 2. FIX: Safely aggregate optional rain/snow volume for the 3h period
                # Use .get() to safely handle cases where 'rain' or 'snow' keys are missing
                rain_3h = item.get('rain', {}).get('3h', 0)
                snow_3h = item.get('snow', {}).get('3h', 0)

                daily_weather[day_str]['rain_sum'] += rain_3h
                daily_weather[day_str]['rain_sum'] += snow_3h

        # --- Summary Generation ---
        weather_lines = []
        for i, (day_str, data) in enumerate(daily_weather.items()):
            if not data['temps']: continue  # Skip if no data for the day

            avg_temp = sum(data['temps']) / len(data['temps'])
            # Create a clean, comma-separated list of conditions
            main_desc = ", ".join(data['descriptions'])

            rain_alert = ""
            # Heavy precipitation alert: total daily accumulation > 10mm
            if data['rain_sum'] > 10:
                rain_alert = "** (HEAVY RAIN/SNOW WARNING - Plan INDOOR/COVERED activities)**"

            weather_lines.append(
                f"Day {i + 1} ({day_str}): Avg Temp {int(avg_temp)}°C. "
                f"Conditions: {main_desc.capitalize()}{rain_alert}. "
            )

        return "\n".join(weather_lines)

    except requests.exceptions.RequestException as e:
        return f"(Forecast API Error: {e})"
    except Exception as e:
        return f"(Forecast Parsing/General Error: {e})"


# --- TEST BLOCK ---
if __name__ == "__main__":

    print("--- OpenWeatherMap Forecast Summary Test ---")

    # ⚠️ IMPORTANT: Choose a date 1-3 days in the future for accurate forecast results.
    test_city = "New Delhi"
    # Example: 3 days from the current date (adjust this dynamically for a real test)
    today = date_obj.today()
    test_start_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    test_duration = 4  # Test a 4-day trip

    print(f"\nRequesting forecast for: {test_city}, {test_duration} days starting {test_start_date}")

    # Run the function
    if OPENWEATHER_KEY == "YOUR_OPENWEATHER_KEY":
        print("\nERROR: Please replace 'YOUR_OPENWEATHER_KEY' in the script with your actual key to run the live test.")
    else:
        summary = get_forecast_summary(test_city, test_start_date, test_duration)

        # Display the output (ready for LLM injection)
        print("\n--- LLM-Ready Weather Summary ---")
        print(summary)
        print("-----------------------------------")