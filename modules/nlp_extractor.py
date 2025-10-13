"""
nlp_extractor.py
Extracts destination, dates, and budget from natural language queries.
Uses spaCy + regex.
"""

import re
import spacy
from datetime import datetime, timedelta
import streamlit as st
from spacy.cli import download


# -----------------------------
# Load SpaCy model safely
# -----------------------------
@st.cache_resource
def load_spacy_model():
    """Load or download SpaCy model once per Streamlit session."""
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        from spacy.cli import download
        download("en_core_web_sm")
        return spacy.load("en_core_web_sm")

nlp = load_spacy_model()


def extract_entities(user_input):
    """
    Extract destination, travel month, duration, and budget from user query.
    """
    doc = nlp(user_input)
    destination = None
    budget = None
    duration = None
    month = None

    # 1️⃣ Destination (city/country)
    for ent in doc.ents:
        if ent.label_ == "GPE":
            destination = ent.text
            break

    # 2️⃣ Budget (captures $1000, under 1200 dollars, etc.)
    budget_match = re.search(r"(?:under|below|less than)?\s*\$?\s?(\d{2,5})", user_input, re.IGNORECASE)
    if budget_match:
        budget = int(budget_match.group(1))

    # 3️⃣ Duration (e.g., 4-day, 5 nights)
    duration_match = re.search(r"(\d+)\s*[- ]?(day|days|night|nights)", user_input, re.IGNORECASE)
    if duration_match:
        duration = int(duration_match.group(1))

    # 4️⃣ Month or travel period
    month_match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December|next month|this month)",
        user_input, re.IGNORECASE
    )
    if month_match:
        month_raw = month_match.group(1).lower()
        if "next" in month_raw:
            next_month = (datetime.now().month % 12) + 1
            month = datetime(datetime.now().year, next_month, 1).strftime("%B %Y")
        elif "this" in month_raw:
            month = datetime.now().strftime("%B %Y")
        else:
            month = month_match.group(1).capitalize() + f" {datetime.now().year}"
    else:
        # Default fallback
        next_month = (datetime.now().month % 12) + 1
        month = datetime(datetime.now().year, next_month, 1).strftime("%B %Y")

    return {
        "destination": destination,
        "budget": budget,
        "duration": duration,
        "date": month,
    }


if __name__ == "__main__":
    # 🔍 Quick test
    q = "Plan a 4-day trip to Boston in November under $800"
    print(extract_entities(q))
