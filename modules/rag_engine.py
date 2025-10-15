import os
import json
import sys

import numpy as np
import logging # <--- ADDED: Python logging module

# Configure the logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Set default log level for this module

# Set environment variable to suppress potential MKL warnings/errors
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import faiss
from openai import OpenAI
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from config.config import (
    OPENAI_API_KEY,
    CACHE_FILE as DATA_FILE,
    FAISS_INDEX_FILE as INDEX_FILE,
    EMBEDDINGS_FILE,
    META_FILE,
    USE_OFFLINE_MODE,
)

if not OPENAI_API_KEY:
    # If the key is still missing, we raise an error.
    raise ValueError(
        "OpenAI API Key not found. Please set OPENAI_API_KEY in config/config.py or as an environment variable."
    )

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


# =====================================================================
# --- Data Loading and Index Building Functions ---
# =====================================================================


def load_and_normalize_data(data_file=DATA_FILE):
    """Load attractions.json and normalize all records for embedding."""
    # CHANGED: Replaced print() with logger.info()
    logger.info(f"Loading data from {data_file}")

    # Ensure 'data' directory exists for config files
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

    # Handle case where attractions.json might not exist yet
    if not os.path.exists(data_file):
        # CHANGED: Replaced print() with logger.warning()
        logger.warning(f"⚠️ Data file not found at {data_file}. Please ensure you have your attractions data.")
        return []

    # ... (rest of function remains the same)
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {data_file}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error loading data file {data_file}: {e}")
        return []

    entries = []
    # Normalize data structures
    for item in data:
        # Create a combined description for embedding
        combined_text = (
            f"Name: {item.get('name', '')}. "
            f"Category: {item.get('category', '')}. "
            f"City: {item.get('city', '')}. "
            f"Description: {item.get('description', '')}"
        )
        if combined_text.strip():
            item["combined_text"] = combined_text
            entries.append(item)

    logger.info(f"Successfully loaded and normalized {len(entries)} entries.")
    return entries


def get_embedding(text):
    """Generates an embedding for a given text using the OpenAI model."""
    if USE_OFFLINE_MODE:
        return np.zeros(1536)  # Return dummy embedding in offline mode

    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return np.array(response.data[0].embedding, dtype=np.float32)
    except Exception as e:
        logger.error(f"OpenAI Embedding API error: {e}")
        return None


def build_embeddings(entries):
    """Generates embeddings and builds the FAISS index."""
    if USE_OFFLINE_MODE:
        logger.warning("Offline mode active. Skipping embedding generation and FAISS index build.")
        return

    embeddings = []
    metadata = []
    logger.info(f"Starting to generate embeddings for {len(entries)} entries...")

    # Load existing indices to avoid regenerating all embeddings
    if os.path.exists(EMBEDDINGS_FILE) and os.path.exists(META_FILE):
        logger.info("Existing embeddings found. Skipping regeneration.")
        # Load the index and metadata
        try:
            index = faiss.read_index(INDEX_FILE)
            with open(META_FILE, 'r') as f:
                metadata = json.load(f)
            logger.info(f"Loaded existing index with {index.ntotal} vectors.")
            return index, metadata
        except Exception as e:
            logger.warning(f"Failed to load existing FAISS index/metadata: {e}. Rebuilding index.")
            # Continue to rebuild if loading fails

    # Actual building process
    for entry in entries:
        embedding = get_embedding(entry["combined_text"])
        if embedding is not None:
            embeddings.append(embedding)
            # Store only essential metadata for the search result
            metadata.append({
                "name": entry.get("name"),
                "city": entry.get("city"),
                "category": entry.get("category"),
                "rating": entry.get("rating"),
                "reviews": entry.get("reviews"),
                "link": entry.get("link"),
                "photo": entry.get("photo"),
            })

    if not embeddings:
        logger.error("No embeddings could be generated. Cannot build index.")
        return None, None

    embeddings_array = np.vstack(embeddings)
    dim = embeddings_array.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings_array)

    # Save the index and metadata
    try:
        faiss.write_index(index, INDEX_FILE)
        with open(META_FILE, 'w') as f:
            json.dump(metadata, f)
        logger.info(f"FAISS index built and saved successfully with {index.ntotal} vectors.")
        return index, metadata
    except Exception as e:
        logger.error(f"Failed to save FAISS index or metadata: {e}")
        return None, None


def load_index():
    """Load the FAISS index and metadata from disk."""
    if USE_OFFLINE_MODE:
        logger.warning("Offline mode active. Cannot load FAISS index.")
        return None, None

    if not os.path.exists(INDEX_FILE) or not os.path.exists(META_FILE):
        logger.warning("FAISS index or metadata file missing. Please run build_embeddings first.")
        return None, None

    try:
        index = faiss.read_index(INDEX_FILE)
        with open(META_FILE, 'r') as f:
            metadata = json.load(f)
        logger.info(f"Loaded FAISS index with {index.ntotal} vectors.")
        return index, metadata
    except Exception as e:
        logger.error(f"Error loading FAISS index or metadata: {e}")
        return None, None


def search_attractions(query, destination_city, top_k=5):
    """Searches the FAISS index for attractions relevant to the query."""
    index, metadata = load_index()
    if index is None or metadata is None:
        logger.error("Search failed: RAG index not available.")
        return []

    query_embedding = get_embedding(query)
    if query_embedding is None:
        logger.error("Search failed: Could not generate query embedding.")
        return []

    # Reshape for FAISS search
    query_vector = query_embedding.reshape(1, -1)

    # Search the index (D is distances, I is indices)
    D, I = index.search(query_vector, k=index.ntotal) # Search the whole index for now

    # Map indices back to attraction metadata
    all_results = [metadata[i] for i in I[0]]

    # Filter by destination city and limit to top_k
    city_filtered_results = []
    for attraction in all_results:
        # Check if the city metadata matches the requested destination
        if attraction.get('city', '').lower() == destination_city.lower():
            city_filtered_results.append(attraction)

        # Stop once we have reached the desired number of results
        if len(city_filtered_results) >= top_k:
            break

    results = city_filtered_results

    # CHANGED: Replaced print() with logger.info()
    logger.info(f"🔍 Top {len(results)} results for: '{query}' (Filtered for {destination_city})")
    return results


# =============================================================
# ✅ Lightweight Wrapper Class for Travel Agent Integration
# =============================================================
class RAGEngine:
    """Simple wrapper around the above RAG functions."""

    def __init__(self):
        pass

    def load_data(self):
        return load_and_normalize_data()

    def build_index(self, entries):
        # Note: This is synchronous now
        return build_embeddings(entries)

    def search(self, query, destination_city, top_k=5):
        return search_attractions(query, destination_city, top_k)


if __name__ == "__main__":
    entries = load_and_normalize_data()
    if entries:
        # Example of manually running the build
        build_embeddings(entries)

        # Example of searching
        results = search_attractions("Top Places to see culture in London", "London")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['name']} - {r.get('city', 'N/A')} ({r.get('rating', 'N/A')})")
