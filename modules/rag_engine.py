import os
import json
import numpy as np

# Set environment variable to suppress potential MKL warnings/errors
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import faiss
from openai import OpenAI
import threading  # <-- New Import

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

# ======================================================================
# --- Threading State Management ---
# ======================================================================
# Global flag to track the RAG build status across threads
RAG_BUILD_IN_PROGRESS = False
# Lock to prevent race conditions when checking/setting the flag
RAG_BUILD_LOCK = threading.Lock()


# ======================================================================
# --- Data Loading and Index Building Functions ---
# ======================================================================

def load_and_normalize_data(data_file=DATA_FILE):
    """Load attractions.json and normalize all records for embedding."""
    # ... (Keep your existing implementation of load_and_normalize_data) ...
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
            # Safely extract key fields
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

    print(f"✅ Loaded and normalized {len(all_entries)} attractions across {len(data)} cities.")
    return all_entries


def build_embeddings(entries):
    """Create embeddings for attractions and build FAISS index (the SLOW part)."""
    # ... (Keep your existing implementation of build_embeddings) ...
    if not entries:
        print("🛑 No entries to embed. Skipping index build.")
        return None

    texts = [entry["text"] for entry in entries]
    embeddings = []

    # Ensure output directories exist
    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)

    if USE_OFFLINE_MODE:
        print("🟡 Running in OFFLINE MODE — generating random embeddings.")
        # Ensure correct dimension (1536 for text-embedding-3-small)
        embeddings = [np.random.rand(1536).tolist() for _ in texts]
    else:
        print("🟢 Building embeddings with OpenAI...")
        for i in range(0, len(texts), 50):
            batch = texts[i:i + 50]
            print(f"Embedding batch {i // 50 + 1}/{(len(texts) // 50) + 1}")
            try:
                response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=batch
                )
                batch_embeds = [d.embedding for d in response.data]
                embeddings.extend(batch_embeds)
            except Exception as e:
                print(f"❌ Error during OpenAI embedding: {e}")
                return None

    embeddings_np = np.array(embeddings).astype("float32")
    np.save(EMBEDDINGS_FILE, embeddings_np)

    index = faiss.IndexFlatL2(embeddings_np.shape[1])
    index.add(embeddings_np)
    faiss.write_index(index, INDEX_FILE)

    # Ensure 'city' is saved in metadata for later filtering
    metadata_to_save = []
    for entry in entries:
        item = entry["meta"]
        item['city'] = entry['city']
        metadata_to_save.append(item)

    with open(META_FILE, "w") as f:
        json.dump(metadata_to_save, f, indent=2)

    print(f"✅ FAISS index built with {len(entries)} entries. Metadata now includes city field.")
    return index


# ======================================================================
# --- THREADED Index Management Functions (The Fix) ---
# ======================================================================

def _is_index_complete(entries):
    """Quickly checks if index files exist AND if the data size matches the index size."""
    if not (os.path.exists(EMBEDDINGS_FILE) and os.path.exists(INDEX_FILE) and os.path.exists(META_FILE)):
        return False

    try:
        index = faiss.read_index(INDEX_FILE)
        # Check if the number of indexed items matches the current number of data entries
        if index.ntotal == len(entries):
            return True
        else:
            return False
    except Exception:
        # If file reading fails, assume corrupted and needs rebuild
        return False


def _run_index_build(entries):
    """The function executed in the background thread."""
    global RAG_BUILD_IN_PROGRESS
    with RAG_BUILD_LOCK:
        RAG_BUILD_IN_PROGRESS = True

    try:
        build_embeddings(entries)
        print("✅ RAG index rebuilt successfully in background.")
    except Exception as e:
        print(f"❌ RAG index build failed in background thread: {e}")
    finally:
        with RAG_BUILD_LOCK:
            RAG_BUILD_IN_PROGRESS = False


def _ensure_index_is_built():
    """Manages the index build process, launching it in a thread if needed (FAST call)."""
    global RAG_BUILD_IN_PROGRESS

    entries = load_and_normalize_data()
    if not entries:
        return

        # 1. Quick Check: Is the index already complete?
    if _is_index_complete(entries):
        return

    # 2. Check: Is a build already in progress?
    with RAG_BUILD_LOCK:
        if RAG_BUILD_IN_PROGRESS:
            print("⏳ RAG index build already in progress. Skipping launch.")
            return

    # 3. Launch Build: Index is missing or outdated AND not currently running.
    print("🚀 Launched RAG index build in a background thread.")
    thread = threading.Thread(target=_run_index_build, args=(entries,))
    thread.start()


# ======================================================================
# --- Search Function ---
# ======================================================================

def search_attractions(query, destination_city, top_k=5):
    """Search cached attractions using semantic similarity, filtering by city."""

    # 1. Trigger the background check/build (FAST call)
    _ensure_index_is_built()

    # 2. Check if the index is ready NOW
    entries = load_and_normalize_data()
    if not _is_index_complete(entries):
        # Fallback if the index is being built or is corrupt
        print("⚠️ RAG Index is not complete or is currently building. Returning empty results.")
        return []

    # 3. Proceed with the search (SLOW operation)
    embeddings_np = np.load(EMBEDDINGS_FILE)
    index = faiss.read_index(INDEX_FILE)

    with open(META_FILE, "r") as f:
        meta = json.load(f)

    if USE_OFFLINE_MODE:
        print("🟡 Offline mode search: generating random query embedding.")
        q_embed = np.random.rand(1, embeddings_np.shape[1]).astype("float32")
    else:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        )
        q_embed = np.array(response.data[0].embedding, dtype="float32").reshape(1, -1)

    # Search a larger set to ensure we find enough for the target city
    search_k = max(top_k * 5, 20)
    distances, indices = index.search(q_embed, search_k)

    # Filter results by the destination_city
    city_filtered_results = []

    for i in indices[0]:
        attraction = meta[i]
        # Check if the attraction has a city field and it matches the destination (case-insensitive)
        if attraction.get('city', '').lower() == destination_city.lower():
            city_filtered_results.append(attraction)

        # Stop once we have reached the desired number of results
        if len(city_filtered_results) >= top_k:
            break

    results = city_filtered_results

    print(f"🔍 Top {len(results)} results for: '{query}' (Filtered for {destination_city})")
    return results


# ============================================================
# ✅ Lightweight Wrapper Class for Travel Agent Integration
# ============================================================
class RAGEngine:
    """Simple wrapper around the above RAG functions."""

    def __init__(self):
        pass

    def load_data(self):
        return load_and_normalize_data()

    def build_index(self, entries):
        # Note: We now discourage direct calling of this, use search() instead
        return build_embeddings(entries)

        # FIX: Update the search method signature

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