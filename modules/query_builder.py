"""Build enriched retrieval queries from user trip context."""

import re

INTEREST_PATTERNS = {
    "food": r"\b(food|dining|restaurant|cuisine|culinary|eat)\b",
    "museum": r"\b(museum|art|gallery|culture|history|historic)\b",
    "beach": r"\b(beach|ocean|coast|swim|waterfront)\b",
    "nightlife": r"\b(nightlife|bar|club|party|evening)\b",
    "nature": r"\b(nature|park|hike|outdoor|garden|wildlife)\b",
    "shopping": r"\b(shopping|market|mall|boutique)\b",
    "family": r"\b(family|kids|children|theme park)\b",
    "adventure": r"\b(adventure|thrill|extreme|sport)\b",
}


def extract_interest_keywords(user_query: str) -> list[str]:
    """Extract interest keywords from the user query via regex."""
    if not user_query:
        return []
    query_lower = user_query.lower()
    return [label for label, pattern in INTEREST_PATTERNS.items() if re.search(pattern, query_lower)]


def build_retrieval_query(user_query, destination, budget, duration, date=None):
    """Build an enriched retrieval query from structured trip context."""
    interests = extract_interest_keywords(user_query)
    interest_text = ", ".join(interests) if interests else "general sightseeing"

    parts = [
        user_query.strip() if user_query else "",
        f"Destination: {destination}.",
        f"Trip length: {duration} days.",
        f"Budget: ${budget}.",
        f"Interests: {interest_text}.",
        "Prefer highly rated attractions suitable for this budget and trip length.",
    ]
    if date:
        parts.append(f"Start date: {date}.")

    return " ".join(p for p in parts if p)
