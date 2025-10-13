import os

# Read from Streamlit secrets
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY")

USE_OFFLINE_MODE = False  # ✅ Enable this for Streamlit Cloud