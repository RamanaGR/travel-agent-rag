import hashlib
import json
import logging
import os
from datetime import datetime, timezone

import faiss
import numpy as np
from openai import OpenAI

from config.config import (
    CACHE_FILE,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
    USE_OFFLINE_MODE,
    get_index_paths,
)
from modules.query_builder import build_retrieval_query
from modules.retrieval import retrieve_attractions

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

logger = logging.getLogger(__name__)

DATA_FILE = str(CACHE_FILE)

if not OPENAI_API_KEY:
    raise ValueError(
        "OpenAI API key not found. Set OPENAI_API_KEY in your environment or .env file."
    )

client = OpenAI(api_key=OPENAI_API_KEY)

CATEGORY_HINTS = {
    "museum": "culture and indoor exploration",
    "art": "art and photography",
    "historic": "history and architecture",
    "landmark": "sightseeing and landmarks",
    "park": "outdoor and nature",
    "beach": "beach and waterfront",
    "food": "dining and local cuisine",
    "shopping": "shopping and markets",
    "neighborhood": "local neighborhood exploration",
}


def _doc_id(item: dict) -> str:
    key = item.get("link") or item.get("name", "")
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def _parse_rating(rating) -> float:
    try:
        return float(rating)
    except (TypeError, ValueError):
        return 0.0


def _parse_reviews(reviews) -> int:
    try:
        return int(str(reviews).replace(",", "").replace("(", "").replace(")", "").strip())
    except (TypeError, ValueError):
        return 0


def _budget_tier(budget, duration) -> str:
    try:
        daily = float(budget) / max(int(duration), 1)
    except (TypeError, ValueError):
        return "moderate"
    if daily < 100:
        return "budget-friendly"
    if daily < 250:
        return "moderate"
    return "premium"


def _category_hints(category: str) -> str:
    category_lower = (category or "").lower()
    hints = [hint for key, hint in CATEGORY_HINTS.items() if key in category_lower]
    return "; ".join(hints) if hints else "general sightseeing"


def _combined_text(item, city="", budget=None, duration=None):
    """Build enriched document text for embedding and BM25."""
    rating = _parse_rating(item.get("rating"))
    reviews = _parse_reviews(item.get("reviews"))
    category = item.get("category", "N/A")
    description = item.get("description", "N/A")
    tier = _budget_tier(budget, duration) if budget and duration else "moderate"

    quality_parts = []
    if rating >= 4.5:
        quality_parts.append(f"Highly rated ({rating} stars")
    elif rating >= 4.0:
        quality_parts.append(f"Well rated ({rating} stars")
    elif rating:
        quality_parts.append(f"Rated {rating} stars")

    if reviews and quality_parts:
        quality_parts[-1] = f"{quality_parts[-1]}, {reviews:,} reviews)"
    elif reviews:
        quality_parts.append(f"Popular ({reviews:,} reviews)")
    elif quality_parts:
        quality_parts[-1] = f"{quality_parts[-1]})"

    quality_str = " ".join(quality_parts)
    hints = _category_hints(category)
    desc_part = description if description and description != "N/A" else hints

    return (
        f"Name: {item.get('name', '')}. "
        f"Category: {category}. City: {city or item.get('city', '')}. "
        f"{quality_str}. "
        f"Good for: {hints}. Budget tier: {tier}. "
        f"Description: {desc_part}."
    )


def prepare_entries(attractions, city, budget=None, duration=None):
    """Normalize attraction records for embedding and indexing."""
    entries = []
    for item in attractions:
        entry = dict(item)
        entry["city"] = city
        entry["doc_id"] = _doc_id(item)
        entry["combined_text"] = _combined_text(item, city, budget, duration)
        entry["search_text"] = entry["combined_text"]
        entries.append(entry)
    return entries


def load_and_normalize_data(data_file=DATA_FILE):
    """Load attractions.json and normalize all records for embedding."""
    logger.info("Loading data from %s", data_file)
    os.makedirs(os.path.dirname(data_file), exist_ok=True)

    if not os.path.exists(data_file):
        logger.warning("Data file not found at %s", data_file)
        return []

    try:
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Error loading data file %s: %s", data_file, e)
        return []

    entries = []
    if isinstance(data, dict):
        for city, attractions in data.items():
            entries.extend(prepare_entries(attractions, city))
    elif isinstance(data, list):
        for item in data:
            city = item.get("city", "")
            entries.append(prepare_entries([item], city)[0])

    logger.info("Loaded and normalized %s entries.", len(entries))
    return entries


def get_embedding(text):
    """Generate an embedding for the given text."""
    if USE_OFFLINE_MODE:
        return np.zeros(1536, dtype=np.float32)

    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        return np.array(response.data[0].embedding, dtype=np.float32)
    except Exception as e:
        logger.error("OpenAI embedding API error: %s", e)
        return None


def _load_embeddings_cache(paths: dict) -> dict:
    cache_path = str(paths["embeddings_cache"])
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_embeddings_cache(paths: dict, cache: dict):
    os.makedirs(paths["dir"], exist_ok=True)
    with open(paths["embeddings_cache"], "w", encoding="utf-8") as f:
        json.dump(cache, f)


def index_exists(city: str) -> bool:
    paths = get_index_paths(city)
    return paths["index"].exists() and paths["meta"].exists()


def load_index(city: str):
    """Load per-city FAISS index and metadata."""
    if USE_OFFLINE_MODE:
        return None, None, None

    paths = get_index_paths(city)
    index_path = str(paths["index"])
    meta_path = str(paths["meta"])
    emb_path = str(paths["embeddings"])

    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        return None, None, None

    try:
        index = faiss.read_index(index_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        embeddings = None
        if os.path.exists(emb_path):
            embeddings = np.load(emb_path)
        logger.info("Loaded FAISS index for %s with %s vectors.", city, index.ntotal)
        return index, metadata, embeddings
    except Exception as e:
        logger.error("Error loading index for %s: %s", city, e)
        return None, None, None


def build_embeddings(entries, city: str, budget=None, duration=None):
    """Generate embeddings with cache and build per-city FAISS index."""
    if USE_OFFLINE_MODE:
        logger.warning("Offline mode active. Skipping embedding generation.")
        return None, None

    if not entries:
        logger.error("No entries provided. Cannot build index.")
        return None, None

    paths = get_index_paths(city)
    os.makedirs(paths["dir"], exist_ok=True)
    cache = _load_embeddings_cache(paths)

    embeddings = []
    metadata = []
    logger.info("Generating embeddings for %s entries in %s...", len(entries), city)

    for entry in entries:
        doc_id = entry["doc_id"]
        text = entry["combined_text"]
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

        cached = cache.get(doc_id)
        if cached and cached.get("text_hash") == text_hash:
            embedding = np.array(cached["embedding"], dtype=np.float32)
        else:
            embedding = get_embedding(text)
            if embedding is not None:
                cache[doc_id] = {
                    "text_hash": text_hash,
                    "embedding": embedding.tolist(),
                }

        if embedding is not None:
            embeddings.append(embedding)
            metadata.append({
                "doc_id": doc_id,
                "name": entry.get("name"),
                "city": entry.get("city"),
                "category": entry.get("category"),
                "rating": entry.get("rating"),
                "reviews": entry.get("reviews"),
                "link": entry.get("link"),
                "photo": entry.get("photo"),
                "description": entry.get("description", "N/A"),
                "combined_text": entry.get("combined_text"),
                "search_text": entry.get("search_text"),
            })

    if not embeddings:
        logger.error("No embeddings generated. Cannot build index.")
        return None, None

    embeddings_array = np.vstack(embeddings)
    index = faiss.IndexFlatL2(embeddings_array.shape[1])
    index.add(embeddings_array)

    faiss.write_index(index, str(paths["index"]))
    np.save(str(paths["embeddings"]), embeddings_array)
    with open(paths["meta"], "w", encoding="utf-8") as f:
        json.dump(metadata, f)

    manifest = {
        "city": city,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "attraction_count": len(metadata),
        "embedding_model": EMBEDDING_MODEL,
    }
    with open(paths["manifest"], "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    _save_embeddings_cache(paths, cache)
    logger.info("FAISS index built for %s with %s vectors.", city, index.ntotal)
    return index, metadata


def ensure_index_for_city(city: str, attractions: list, budget=None, duration=None) -> bool:
    """Build or refresh per-city index from attraction list."""
    entries = prepare_entries(attractions, city, budget, duration)
    index, metadata = build_embeddings(entries, city, budget, duration)
    return index is not None and metadata is not None


def search_attractions(
    query,
    destination_city,
    top_k=8,
    user_query="",
    budget=None,
    duration=None,
    selected_only: list | None = None,
):
    """Hybrid search over per-city index."""
    _, metadata, embeddings = load_index(destination_city)
    if not metadata:
        logger.error("Search failed: no index for %s", destination_city)
        return []

    if selected_only:
        selected_ids = {_doc_id(s) for s in selected_only}
        filtered_meta = []
        filtered_emb = []
        for i, item in enumerate(metadata):
            if item.get("doc_id") in selected_ids:
                filtered_meta.append(item)
                if embeddings is not None and i < len(embeddings):
                    filtered_emb.append(embeddings[i])
        metadata = filtered_meta
        embeddings = np.vstack(filtered_emb) if filtered_emb else None

    query_embedding = get_embedding(query)
    if query_embedding is None:
        return []

    return retrieve_attractions(
        query=query,
        city=destination_city,
        candidates=metadata,
        query_embedding=query_embedding,
        embeddings_matrix=embeddings,
        user_query=user_query or query,
        top_k=top_k,
    )


def retrieve_for_trip(
    user_query,
    destination,
    budget,
    duration,
    date=None,
    top_k=8,
    selected_attractions=None,
):
    """High-level retrieval using enriched query and hybrid ranking."""
    query = build_retrieval_query(user_query, destination, budget, duration, date)
    return search_attractions(
        query=query,
        destination_city=destination,
        top_k=top_k,
        user_query=user_query,
        budget=budget,
        duration=duration,
        selected_only=selected_attractions,
    )


# Backward-compatible aliases
INDEX_FILE = str(get_index_paths("_legacy")["index"])
META_FILE = str(get_index_paths("_legacy")["meta"])


class RAGEngine:
    """Wrapper around RAG functions."""

    def load_data(self):
        return load_and_normalize_data()

    def build_index(self, entries, city: str, budget=None, duration=None):
        return build_embeddings(entries, city, budget, duration)

    def search(self, query, destination_city, top_k=8, **kwargs):
        return search_attractions(query, destination_city, top_k=top_k, **kwargs)
