import os
import json
import numpy as np

# Set environment variable to suppress potential MKL warnings/errors
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import faiss
from openai import OpenAI

from config.config import (
    OPENAI_API_KEY,
    CACHE_FILE as DATA_FILE,
    FAISS_INDEX_FILE as INDEX_FILE,
    EMBEDDINGS_FILE,
    META_FILE,
    USE_OFFLINE_MODE,
)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


# =====================================================================
# --- Data Loading and Index Building Functions ---
# =====================================================================

def load_and_normalize_data(data_file=DATA_FILE):
    """Load attractions.json and normalize all records for embedding."""
    print(f"Loading data from {data_file}")

    # Ensure 'data' directory exists for config files
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

    # Handle case where attractions.json might not exist yet
    if not os.path.exists(data_file):
        print(f"⚠️ Data file not found at {data_file}. Returning empty list.")
        return []

    with open(data_file, "r") as f:
        data = json.load(f)

    all_entries = []
    for city, attractions in data.items():
        for item in attractions:
            # Safely extract key fields (different APIs have different names)
            name = item.get("name", "")
            desc = item.get("description", "")
            category = item.get("category", "")
            rating = item.get("rating", "")
            reviews = item.get("reviews", "")

            # Build unified descriptive text for embedding
            text = f"{name}. {desc} {category} Rated {rating} with {reviews} reviews. Located in {city}."
            text = text.strip()

            all_entries.append({
                "city": city,
                "name": name,
                "text": text,
                "meta": item
            })

    print(f"Total entries loaded: {len(all_entries)}")
    return all_entries


def build_embeddings(entries):
    """Generates embeddings and builds a FAISS index synchronously."""

    if not entries:
        print("🔴 Cannot build index: No entries loaded.")
        return

    print("Starting synchronous embedding generation and index build...")

    texts = [entry["text"] for entry in entries]
    meta_data = [entry["meta"] for entry in entries]

    if USE_OFFLINE_MODE:
        # Create random embeddings for offline testing
        embeddings = np.random.rand(len(texts), 1536).astype("float32")
    else:
        # Call OpenAI to generate embeddings
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        embeddings = np.array([d.embedding for d in response.data], dtype="float32")

    # Save embeddings and metadata
    np.save(EMBEDDINGS_FILE, embeddings)
    with open(META_FILE, "w") as f:
        json.dump(meta_data, f)

    # Build FAISS index
    d = embeddings.shape[1]  # Dimension of the embeddings (e.g., 1536)
    index = faiss.IndexFlatL2(d)
    index.add(embeddings)
    faiss.write_index(index, INDEX_FILE)

    print(f"✅ Index built with {index.ntotal} vectors and saved successfully.")


def search_attractions(query: str, destination_city: str, top_k: int = 5):
    """Search the FAISS index for the most relevant attractions, filtered by city."""

    if not os.path.exists(INDEX_FILE) or not os.path.exists(META_FILE):
        print("⚠️ RAG Index files not found. Returning empty list.")
        return []

    # Load index and metadata
    index = faiss.read_index(INDEX_FILE)

    with open(META_FILE, "r") as f:
        meta = json.load(f)

    if USE_OFFLINE_MODE:
        print("🟡 Offline mode search: generating random query embedding.")
        q_embed = np.random.rand(1, 1536).astype("float32")
    else:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        q_embed = np.array(response.data[0].embedding, dtype="float32").reshape(1, -1)

    # Search the index for more than 'top_k' results to allow for filtering
    search_k = max(top_k * 5, 25)
    distances, indices = index.search(q_embed, search_k)
    raw_results = [meta[i] for i in indices[0]]

    # Filter by destination city
    city_filtered_results = []
    for attraction in raw_results:
        # Check if the city metadata matches the requested destination
        if attraction.get('city', '').lower() == destination_city.lower():
            city_filtered_results.append(attraction)

        # Stop once we have reached the desired number of results
        if len(city_filtered_results) >= top_k:
            break

    results = city_filtered_results

    print(f"🔍 Top {len(results)} results for: '{query}' (Filtered for {destination_city})")
    return results


# ============================================================\
# ✅ Lightweight Wrapper Class for Travel Agent Integration
# ============================================================\
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