"""
nlp_extractor.py
Extracts destination, dates, and budget from natural language queries.
Uses spaCy + regex.
"""

import re
import spacy
from datetime import datetime, timedelta

# Load spaCy model
nlp = spacy.load("en_core_web_sm")


def extract_entities(user_input):
    """
    Extract destination city, travel dates, and budget from user input.
    """
    doc = nlp(user_input)
    destination = None
    start_date = None
    end_date = None
    budget = None
    duration_days = None

    # 1️⃣ Detect destination (GPE = city/country)
    for ent in doc.ents:
        if ent.label_ == "GPE":
            destination = ent.text
            break

    # 2️⃣ Detect budget ($ or “under 1000 dollars” etc.)
    budget_match = re.search(r"\$?\s?(\d{2,5})\s?(USD|dollars|bucks|usd)?", user_input, re.IGNORECASE)
    if budget_match:
        budget = int(budget_match.group(1))

    # 3️⃣ Detect number of days (e.g., “3-day trip”)
    duration_match = re.search(r"(\d+)\s*[- ]?\s*(day|days|night|nights)", user_input, re.IGNORECASE)
    if duration_match:
        duration_days = int(duration_match.group(1))

    # 4️⃣ Detect month or date (simple pattern)
    month_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)", user_input, re.IGNORECASE)
    if month_match:
        month_name = month_match.group(1).capitalize()
        year = datetime.now().year
        start_date = f"{month_name} {year}"
        if duration_days:
            # Roughly add duration
            end_date = f"{month_name} {year}"
    else:
        # Default to next month
        next_month = (datetime.now().month % 12) + 1
        start_date = datetime(datetime.now().year, next_month, 1).strftime("%B %Y")
        end_date = start_date

    return {
        "destination": destination,
        "budget": budget,
        "duration_days": duration_days,
        "start_date": start_date,
        "end_date": end_date,
    }


if __name__ == "__main__":
    # 🔍 Quick test
    q = "Plan a 4-day trip to Boston in November under $800"
    print(extract_entities(q))
