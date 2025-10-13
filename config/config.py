import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- API KEYS ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

# --- API HOSTS & ENDPOINTS ---
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "travel-advisor.p.rapidapi.com")
OPENWEATHER_ENDPOINT = os.getenv("OPENWEATHER_ENDPOINT", "https://api.openweathermap.org/data/2.5/weather")

# --- DATA DIRECTORIES ---
# DATA_DIR = os.getenv("DATA_DIR", os.path.join(PROJECT_ROOT, "data"))
# LOG_DIR = os.getenv("LOG_DIR", os.path.join(PROJECT_ROOT, "logs"))
DATA_DIR = os.path.join(PROJECT_ROOT, os.getenv("DATA_DIR"))
LOG_DIR = os.path.join(PROJECT_ROOT, os.getenv("LOG_DIR"))

# --- COMMON DATA FILES ---
CACHE_FILE = os.path.join(DATA_DIR, "attractions.json")
COUNTER_FILE = os.path.join(DATA_DIR, "attractions_counter.txt")
GEOID_CACHE_FILE = os.path.join(DATA_DIR, "geoids.json")

# --- RAG FILES ---
FAISS_INDEX_FILE = os.path.join(DATA_DIR, "faiss_index.bin")
EMBEDDINGS_FILE = os.path.join(DATA_DIR, "attraction_embeddings.npy")
META_FILE = os.path.join(DATA_DIR, "attraction_meta.json")

# --- RAG CONFIG ---
USE_OFFLINE_MODE = os.getenv("USE_OFFLINE_MODE", "False").lower() == "true"

# --- Utility print (optional) ---
if __name__ == "__main__":
    print("✅ Config loaded successfully:")
    print(f"OpenAI Key present: {'Yes' if OPENAI_API_KEY else 'No'}")
    print(f"RapidAPI Host: {RAPIDAPI_HOST}")
    print(f"Project Root: {PROJECT_ROOT}")  # NEW: Verify root
    print(f"Data directory (absolute): {DATA_DIR}")
    print(f"Cache File (absolute): {CACHE_FILE}")
    print(f"FAISS index file: {FAISS_INDEX_FILE}")
