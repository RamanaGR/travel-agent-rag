import json
import re
import spacy

nlp = spacy.load("en_core_web_sm")

def parse_user_query(query):
    doc = nlp(query)
    location, days, budget = None, None, None

    # spaCy entities
    for ent in doc.ents:
        if ent.label_ == "GPE":
            location = ent.text
        elif ent.label_ == "MONEY":
            budget = ent.text

    # simple regex fallback for days e.g. "3-day" or "3 days"
    m = re.search(r"(\d+)\s*[- ]?\s*(day|days)", query, flags=re.I)
    if m:
        days = m.group(1) + " day(s)"

    return {"location": location, "days": days, "budget": budget}

def generate_itinerary(parsed):
    # simple placeholder plan sized by parsed days if numeric; otherwise 3 default days
    try:
        num_days = int(re.search(r"(\d+)", str(parsed.get("days") or "3")).group(1))
    except Exception:
        num_days = 3

    plan = []
    for d in range(1, num_days+1):
        plan.append({"day": d, "activities": ["Explore downtown", "Try local cuisine"]})

    itinerary = {
        "destination": parsed.get("location") or "Unknown",
        "duration_days": num_days,
        "budget": parsed.get("budget") or "Not given",
        "plan": plan
    }
    return itinerary

if __name__ == "__main__":
    q = input("Enter your travel request: ")
    parsed = parse_user_query(q)
    itinerary = generate_itinerary(parsed)
    print(json.dumps(itinerary, indent=4))
