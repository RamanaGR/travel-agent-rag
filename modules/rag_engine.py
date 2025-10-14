import os
import json
import numpy as np

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
    """Create embeddings for attractions and build FAISS index."""
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
                # Fallback or error handling needed here if API fails entirely
                return None

    embeddings_np = np.array(embeddings).astype("float32")
    np.save(EMBEDDINGS_FILE, embeddings_np)

    index = faiss.IndexFlatL2(embeddings_np.shape[1])
    index.add(embeddings_np)
    faiss.write_index(index, INDEX_FILE)

    # FIX: Ensure 'city' is saved in metadata for later filtering
    metadata_to_save = []
    for entry in entries:
        item = entry["meta"]
        item['city'] = entry['city']
        metadata_to_save.append(item)

    with open(META_FILE, "w") as f:
        json.dump(metadata_to_save, f, indent=2)

    print(f"✅ FAISS index built with {len(entries)} entries. Metadata now includes city field.")
    return index


# NEW: Helper function to check and build the index
def _ensure_index_is_built():
    """Checks if index files exist; if not, loads data and rebuilds them."""
    if not (os.path.exists(EMBEDDINGS_FILE) and os.path.exists(INDEX_FILE) and os.path.exists(META_FILE)):
        print("🚨 RAG index files not found or incomplete. Building index...")
        entries = load_and_normalize_data()
        if entries:
            build_embeddings(entries)
            print("✅ RAG index rebuilt successfully.")
        else:
            print("⚠️ Cannot build RAG index: No attraction data found.")
            raise FileNotFoundError("RAG index data (attractions.json) is missing or empty.")


def search_attractions(query, destination_city, top_k=5):
    """Search cached attractions using semantic similarity, filtering by city."""

    # FIX: Ensure the index is available before attempting to load
    try:
        _ensure_index_is_built()
    except FileNotFoundError:
        # If the index cannot be built (e.g., no source data), return empty results
        return []

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

    # Search a larger number of results (e.g., 5x top_k) to ensure we find enough for the target city
    search_k = max(top_k * 5, 20)
    distances, indices = index.search(q_embed, search_k)

    # FIX: Filter results by the destination_city
    city_filtered_results = []

    for i in indices[0]:
        attraction = meta[i]
        # Check if the attraction has a city field and it matches the destination (case-insensitive)
        if attraction.get('city', '').lower() == destination_city.lower():
            city_filtered_results.append(attraction)

        # Stop once we have reached the desired number of results
        if len(city_filtered_results) >= top_k:
            break

    # Return the filtered set
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
        # build_embeddings already has the fix
        return build_embeddings(entries)

    # FIX: Update the search method signature
    def search(self, query, destination_city, top_k=5):
        return search_attractions(query, destination_city, top_k)


if __name__ == "__main__":
    entries = load_and_normalize_data()
    if entries:
        build_embeddings(entries)
        results = search_attractions("Top Places to see culture in London", "London")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['name']} - {r.get('city', 'N/A')} ({r.get('rating', 'N/A')})")