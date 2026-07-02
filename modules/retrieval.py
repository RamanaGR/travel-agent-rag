"""Hybrid retrieval: BM25 + vector fusion with metadata reranking."""

import logging
import re
from difflib import SequenceMatcher

import numpy as np
from rank_bm25 import BM25Okapi

from modules.query_builder import extract_interest_keywords

logger = logging.getLogger(__name__)

RRF_K = 60


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _parse_rating(rating) -> float:
    try:
        return float(rating)
    except (TypeError, ValueError):
        return 0.0


def _parse_reviews(reviews) -> int:
    if reviews is None:
        return 0
    try:
        return int(str(reviews).replace(",", "").replace("(", "").replace(")", "").strip())
    except ValueError:
        return 0


def metadata_score(attraction: dict, interests: list[str]) -> float:
    """Score attraction quality and interest alignment from metadata."""
    rating = _parse_rating(attraction.get("rating"))
    reviews = _parse_reviews(attraction.get("reviews"))
    category = (attraction.get("category") or "").lower()
    search_text = (attraction.get("search_text") or attraction.get("combined_text") or "").lower()

    score = 0.0
    if rating >= 4.5:
        score += 0.3
    elif rating >= 4.0:
        score += 0.15

    if reviews >= 5000:
        score += 0.2
    elif reviews >= 1000:
        score += 0.1

    for interest in interests:
        if interest in category or interest in search_text:
            score += 0.15

    return min(score, 1.0)


def reciprocal_rank_fusion(rankings: list[list[str]], weights: list[float] | None = None) -> dict[str, float]:
    """Combine multiple ranked lists using weighted reciprocal rank fusion."""
    if weights is None:
        weights = [1.0] * len(rankings)

    scores: dict[str, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (RRF_K + rank + 1)
    return scores


def vector_rank(query_embedding: np.ndarray, embeddings: np.ndarray, doc_ids: list[str]) -> list[str]:
    """Rank documents by cosine similarity to the query embedding."""
    if len(doc_ids) == 0:
        return []

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = embeddings / norms

    query_norm = np.linalg.norm(query_embedding)
    if query_norm == 0:
        return doc_ids

    query_vec = query_embedding / query_norm
    similarities = normalized @ query_vec
    order = np.argsort(-similarities)
    return [doc_ids[i] for i in order]


def bm25_rank(query: str, candidates: list[dict]) -> list[str]:
    """Rank candidates using BM25 over search text."""
    if not candidates:
        return []

    corpus = [_tokenize(c.get("search_text") or c.get("combined_text") or c.get("name", "")) for c in candidates]
    if not any(corpus):
        return [c["doc_id"] for c in candidates]

    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenize(query))
    order = np.argsort(-scores)
    return [candidates[i]["doc_id"] for i in order]


def build_match_reason(attraction: dict, interests: list[str], score: float) -> str:
    """Human-readable explanation for why an attraction was retrieved."""
    parts = []
    rating = _parse_rating(attraction.get("rating"))
    if rating >= 4.5:
        parts.append("highly rated")
    if interests:
        category = (attraction.get("category") or "").lower()
        matched = [i for i in interests if i in category]
        if matched:
            parts.append(", ".join(matched))
    if score >= 0.8:
        parts.append("strong match")
    elif score >= 0.5:
        parts.append("good match")
    return "Matched: " + ", ".join(parts) if parts else "Matched: relevance"


def retrieve_attractions(
    query: str,
    city: str,
    candidates: list[dict],
    query_embedding: np.ndarray | None,
    embeddings_matrix: np.ndarray | None,
    user_query: str = "",
    top_k: int = 8,
) -> list[dict]:
    """
    Hybrid retrieval over city-scoped candidates.
    Returns candidates enriched with retrieval_score and match_reason.
    """
    if not candidates:
        return []

    interests = extract_interest_keywords(user_query or query)
    doc_ids = [c["doc_id"] for c in candidates]

    rankings = []
    weights = []

    if query_embedding is not None and embeddings_matrix is not None and len(embeddings_matrix) > 0:
        vec_ranking = vector_rank(query_embedding, embeddings_matrix, doc_ids)
        rankings.append(vec_ranking)
        weights.append(1.0)

    bm25_ranking = bm25_rank(query, candidates)
    rankings.append(bm25_ranking)
    weights.append(0.8)

    meta_ranking = sorted(
        doc_ids,
        key=lambda did: metadata_score(next(c for c in candidates if c["doc_id"] == did), interests),
        reverse=True,
    )
    rankings.append(meta_ranking)
    weights.append(0.5)

    fused = reciprocal_rank_fusion(rankings, weights)
    max_score = max(fused.values()) if fused else 1.0

    id_to_candidate = {c["doc_id"]: c for c in candidates}
    ordered_ids = sorted(fused.keys(), key=lambda did: fused[did], reverse=True)

    results = []
    for doc_id in ordered_ids[:top_k]:
        item = dict(id_to_candidate[doc_id])
        norm_score = fused[doc_id] / max_score if max_score else 0.0
        item["retrieval_score"] = round(norm_score, 3)
        item["match_reason"] = build_match_reason(item, interests, norm_score)
        results.append(item)

    logger.info("Hybrid retrieval returned %s results for %s", len(results), city)
    return results


def format_sources_for_prompt(attractions: list[dict]) -> str:
    """Format numbered source list for LLM grounding."""
    if not attractions:
        return "No retrieved attractions available."

    lines = []
    for i, att in enumerate(attractions, 1):
        lines.append(
            f"{i}. {att.get('name', 'Unknown')} | Category: {att.get('category', 'N/A')} | "
            f"Rating: {att.get('rating', 'N/A')} | Reviews: {att.get('reviews', 'N/A')} | "
            f"Link: {att.get('link', 'N/A')}"
        )
    return "\n".join(lines)


def check_grounding(itinerary_data: dict, sources: list[dict], threshold: float = 0.4) -> list[str]:
    """Flag itinerary activities that do not fuzzy-match any retrieved source."""
    if not sources:
        return []

    source_names = [s.get("name", "").lower() for s in sources if s.get("name")]
    warnings = []

    for day in itinerary_data.get("itinerary", []):
        for activity in day.get("activities", []):
            activity_text = activity.get("activity", "").lower()
            best_ratio = 0.0
            for name in source_names:
                if name and name in activity_text:
                    best_ratio = 1.0
                    break
                ratio = SequenceMatcher(None, name, activity_text).ratio()
                best_ratio = max(best_ratio, ratio)
            if best_ratio < threshold:
                warnings.append(activity.get("activity", "Unknown activity"))

    return warnings
