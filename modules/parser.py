import re
import spacy

# Load English NLP model once
nlp = spacy.load("en_core_web_sm")

def parse_user_query(query: str):
    """
    Extracts location, number of days, and budget from a natural language query.
    Example: "Plan a 3-day trip to Miami under $600"
    """
    doc = nlp(query)
    location, days, budget = None, None, None

    for ent in doc.ents:
        if ent.label_ == "GPE":
            location = ent.text
        elif ent.label_ == "MONEY":
            budget = ent.text

    m = re.search(r"(\d+)\s*[- ]?\s*(day|days)", query, flags=re.I)
    if m:
        days = m.group(1) + " day(s)"

    return {"location": location, "days": days, "budget": budget}
