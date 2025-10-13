import os

# -------------------------------
# 🔐 Load environment variables
# (from Streamlit Cloud Secrets or .env locally)
# -------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY")

# -------------------------------
# 🧠 RAG Configuration
# -------------------------------
# Whether to use offline mode (no FAISS writes or heavy API calls)
USE_OFFLINE_MODE = True  # ✅ Keep True for Streamlit Cloud

# -------------------------------
# 📁 Data and File Paths
# -------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Paths used by RAG Engine
CACHE_FILE = os.path.join(DATA_DIR, "attractions.json")
FAISS_INDEX_FILE = os.path.join(DATA_DIR, "faiss_index.bin")
EMBEDDINGS_FILE = os.path.join(DATA_DIR, "attraction_embeddings.npy")
META_FILE = os.path.join(DATA_DIR, "attraction_meta.json")

# -------------------------------
# 🌐 API Endpoints
# -------------------------------
RAPIDAPI_HOST = "travel-advisor.p.rapidapi.com"
OPENWEATHER_ENDPOINT = "https://api.openweathermap.org/data/2.5/weather"

# -------------------------------
# 🧩 General Settings
# -------------------------------
DEBUG = True
APP_NAME = "AI Travel Planner"
