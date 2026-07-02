import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INDEXES_DIR = DATA_DIR / "indexes"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY") or os.getenv("OPENWEATHER_API_KEY")

USE_OFFLINE_MODE = os.getenv("USE_OFFLINE_MODE", "False").lower() in ("true", "1", "yes")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

CACHE_FILE = DATA_DIR / "attractions.json"
COUNTER_FILE = DATA_DIR / "attractions_counter.txt"
GEOID_CACHE_FILE = DATA_DIR / "geoids.json"

# Legacy global paths (kept for backward compatibility)
FAISS_INDEX_FILE = DATA_DIR / "faiss_index.bin"
EMBEDDINGS_FILE = DATA_DIR / "attraction_embeddings.npy"
META_FILE = DATA_DIR / "attraction_meta.json"

WEATHER_COUNTER_FILE = DATA_DIR / "api_usage.txt"
WEATHER_CACHE_FILE = DATA_DIR / "weather_cache.json"

RAPIDAPI_HOST = "travel-advisor.p.rapidapi.com"
OPENWEATHER_ENDPOINT = "https://api.openweathermap.org/data/2.5/forecast"
OPENWEATHER_ENDPOINT_CORD = "https://api.openweathermap.org/geo/1.0/direct"

EMBEDDING_MODEL = "text-embedding-3-small"
APP_NAME = "AI Travel Planner"

VALID_UI_THEMES = ("ocean", "sunset", "minimal", "tropical")
UI_THEME = os.getenv("UI_THEME", "sunset")
if UI_THEME not in VALID_UI_THEMES:
    UI_THEME = "sunset"


def city_slug(city: str) -> str:
    """Normalize city name for filesystem paths."""
    slug = city.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-") or "unknown"


def get_index_paths(city: str) -> dict:
    """Return per-city index file paths."""
    city_dir = INDEXES_DIR / city_slug(city)
    return {
        "dir": city_dir,
        "index": city_dir / "faiss_index.bin",
        "meta": city_dir / "attraction_meta.json",
        "embeddings": city_dir / "attraction_embeddings.npy",
        "embeddings_cache": city_dir / "embeddings_cache.json",
        "manifest": city_dir / "manifest.json",
    }
