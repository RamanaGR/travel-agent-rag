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

    print(f"✅ Loaded and normalized {len(all_entries)} attractions across {len(data)} cities.")
    return all_entries


def build_embeddings(entries):
    """Create embeddings for attractions and build FAISS index."""
    texts = [entry["text"] for entry in entries]
    embeddings = []

    if USE_OFFLINE_MODE:
        print("🟡 Running in OFFLINE MODE — generating random embeddings.")
        embeddings = [np.random.rand(1536).tolist() for _ in texts]
    else:
        print("🟢 Building embeddings with OpenAI...")
        for i in range(0, len(texts), 50):
            batch = texts[i:i+50]
            print(f"Embedding batch {i//50 + 1}/{(len(texts)//50) + 1}")
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=batch
            )
            batch_embeds = [d.embedding for d in response.data]
            embeddings.extend(batch_embeds)

    embeddings_np = np.array(embeddings).astype("float32")
    np.save(EMBEDDINGS_FILE, embeddings_np)

    index = faiss.IndexFlatL2(embeddings_np.shape[1])
    index.add(embeddings_np)
    faiss.write_index(index, INDEX_FILE)

    with open(META_FILE, "w") as f:
        json.dump([entry["meta"] for entry in entries], f, indent=2)

    print(f"✅ FAISS index built with {len(entries)} entries.")
    return index


def search_attractions(query, top_k=5):
    """Search cached attractions using semantic similarity."""
    if not os.path.exists(EMBEDDINGS_FILE):
        raise FileNotFoundError("❌ Embeddings not found. Run build_embeddings() first.")

    embeddings_np = np.load(EMBEDDINGS_FILE)
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

    distances, indices = index.search(q_embed, top_k)
    results = [meta[i] for i in indices[0]]

    print(f"🔍 Top {top_k} results for: '{query}'")
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
        return build_embeddings(entries)

    def search(self, query, top_k=5):
        return search_attractions(query, top_k)

if __name__ == "__main__":
    entries = load_and_normalize_data()
    build_embeddings(entries)
    results = search_attractions("Top Places in Paris")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['name']} - {r.get('category', 'N/A')} ({r.get('rating', 'N/A')})")
