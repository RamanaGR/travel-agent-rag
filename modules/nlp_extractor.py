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
    print("duration match ",duration_match)
    if duration_match:
        duration = int(duration_match.group(1))

    # 4️⃣ Date/Month Extraction (NEW: Specific date first, then month name)

    month = None  # Initialize 'month' which is used for the final return 'date'

    # NEW LOGIC: Check for specific date formats (YYYY-MM-DD, MM/DD/YYYY, etc.)
    # This regex is flexible with hyphens, slashes, and periods
    date_regex = r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})|(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})"
    specific_date_match = re.search(date_regex, user_input)

    if specific_date_match:
        # Get the full matched string (e.g., '2025-02-15' or '02/15/2025')
        date_str = specific_date_match.group(0)

        # Try to parse the date into a standardized YYYY-MM-DD format
        try:
            # Try to parse based on common formats and convert to YYYY-MM-DD
            # The parsing logic in 2_Itinerary_Generator.py is robust, but a standard format helps
            if len(date_str.split(date_str[4])) == 3:  # Simple heuristic for YYYY-MM-DD/YYYY format
                dt_obj = datetime.strptime(date_str, '%Y-%m-%d')
            else:  # Assume MM/DD/YYYY or similar
                dt_obj = datetime.strptime(date_str, '%m-%d-%Y')

            # Use the exact date string for the session state.
            month = dt_obj.strftime('%Y-%m-%d')

        except ValueError:
            # If parsing fails, fall through to the month-name check below
            pass
    if month is None:
        #Month or travel period
        month_match = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December|next month|this month)",
            user_input, re.IGNORECASE
        )
        print(month_match)
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
    else:
        # Default fallback (original logic)
        now = datetime.now()
        next_month = (now.month % 12) + 1
        year = now.year if next_month > now.month else now.year + 1
        month = datetime(year, next_month, 1).strftime("%B %Y")
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
