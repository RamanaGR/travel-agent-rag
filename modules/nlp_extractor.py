"""
nlp_extractor.py
Extracts destination, dates, duration, and budget from natural language queries.
Uses spaCy + regex, aligned with OpenWeatherMap 5-day forecast restriction.
"""

import re
import spacy
from datetime import datetime, timedelta, date as date_obj
import streamlit as st
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Create a logger for this module
logger = logging.getLogger(__name__)

# -----------------------------
# Load SpaCy model safely
# -----------------------------
@st.cache_resource
def load_spacy_model():
    """Load or download SpaCy model once per Streamlit session."""
    logger.info("⚡ Loading SpaCy model 'en_core_web_sm'")
    try:
        nlp = spacy.load("en_core_web_sm")
        logger.info("✅ SpaCy model loaded successfully")
        return nlp
    except OSError:
        logger.warning("⚠️ SpaCy model not found, downloading 'en_core_web_sm'")
        try:
            download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
            logger.info("✅ SpaCy model downloaded and loaded successfully")
            return nlp
        except Exception as e:
            logger.error(f"❌ Failed to download or load SpaCy model: {e}")
            raise

nlp = load_spacy_model()

def extract_entities(user_input):
    """
    Extract destination, date, duration, and budget from user query.
    Ensures dates are within OpenWeatherMap's 5-day forecast limit (from today).
    Returns date in YYYY-MM-DD format.
    """
    logger.info(f"⚡ Extracting entities from query: '{user_input}'")
    doc = nlp(user_input)
    destination = None
    budget = None
    duration = None
    date = None
    today = date_obj.today()

    # 1️⃣ Destination (city/country)
    logger.debug("Extracting destination")
    for ent in doc.ents:
        if ent.label_ == "GPE":
            destination = ent.text
            logger.info(f"✅ Destination extracted: {destination}")
            break
    if not destination:
        logger.warning("⚠️ No destination found in query")
        destination = None

    # 2️⃣ Budget (captures $1000, under 1200 dollars, etc.)
    logger.debug("Extracting budget")
    # Stricter regex to match currency-related numbers only
    budget_match = re.search(r"(?:under|below|less than)?\s*\$?\s*(\d{3,5})\s*(?:dollars|USD)?\b", user_input, re.IGNORECASE)
    if budget_match:
        budget = int(budget_match.group(1))
        logger.info(f"✅ Budget extracted: ${budget}")
    else:
        logger.warning("⚠️ No budget found, setting default to $1000")
        budget = 1000

    # 3️⃣ Duration (e.g., 4-day, 5 nights, or 'weekend')
    logger.debug("Extracting duration")
    duration_match = re.search(r"(\d+)\s*[- ]?(day|days|night|nights)", user_input, re.IGNORECASE)
    if duration_match:
        duration = int(duration_match.group(1))
        logger.info(f"✅ Duration extracted: {duration} days")
    elif "weekend" in user_input.lower():
        duration = 3  # Assume Friday to Sunday
        logger.info(f"✅ Duration extracted for 'weekend': 3 days")
    elif "week" in user_input.lower():
        # Calculate days remaining in 5-day forecast window
        days_remaining = 5  # From today to 5 days ahead
        duration = days_remaining
        logger.info(f"✅ Duration extracted for 'week': {duration} days")
    else:
        logger.warning("⚠️ No duration found, setting default to 1 day")
        duration = 1

    # 4️⃣ Date Extraction (specific dates or relative terms within 5 days)
    logger.debug("Extracting date")
    # Specific date formats (YYYY-MM-DD, MM-DD-YYYY, DD-MM-YYYY)
    date_regex = r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})|(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})"
    specific_date_match = re.search(date_regex, user_input)

    if specific_date_match:
        date_str = specific_date_match.group(0)
        logger.debug(f"Found specific date: {date_str}")
        try:
            # Try parsing different date formats
            if date_str.count('-') == 2 and date_str.startswith('20'):
                dt_obj = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                dt_obj = datetime.strptime(date_str, '%m-%d-%Y')  # Handles MM-DD-YYYY, MM/DD/YYYY
            parsed_date = dt_obj.date()
            # Validate date is within 5 days from today
            if today <= parsed_date <= today + timedelta(days=5):
                date = parsed_date.strftime('%Y-%m-%d')
                logger.info(f"✅ Specific date extracted and validated: {date}")
            else:
                logger.warning(f"⚠️ Specific date {date_str} is outside 5-day forecast window, defaulting to tomorrow")
                date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        except ValueError:
            logger.warning(f"⚠️ Failed to parse specific date {date_str}, checking relative terms")
            date = None
    else:
        # Check for relative date terms
        user_input_lower = user_input.lower()
        if "tomorrow" in user_input_lower:
            date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
            logger.info(f"✅ Relative date 'tomorrow' extracted: {date}")
        elif "weekend" in user_input_lower:
            # Assume "weekend" starts on Friday
            days_to_friday = (4 - today.weekday()) % 7  # Friday is 4 in weekday (0=Mon, 6=Sun)
            if days_to_friday == 0:  # If today is Friday, use today
                days_to_friday = 0
            if days_to_friday <= 5:
                date = (today + timedelta(days=days_to_friday)).strftime('%Y-%m-%d')
                logger.info(f"✅ Relative date 'weekend' extracted (start from Friday): {date}")
            else:
                logger.warning(f"⚠️ 'Weekend' is outside 5-day forecast window, defaulting to tomorrow")
                date = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        elif "week" in user_input_lower:
            # Assume "this week" starts from today
            date = today.strftime('%Y-%m-%d')
            logger.info(f"✅ Relative date 'this week' extracted (start from today): {date}")
        else:
            logger.warning("⚠️ No valid date found, defaulting to tomorrow")
            date = (today + timedelta(days=1)).strftime('%Y-%m-%d')

    result = {
        "destination": destination,
        "budget": budget,
        "duration": duration,
        "date": date,
    }
    logger.info(f"✅ Extraction complete: {result}")
    return result

if __name__ == "__main__":
    # 🔍 Quick tests
    test_queries = [
        "Plan a 4-day trip to Miami starting tomorrow for under $1000",
        "I need a 3-day itinerary for Paris starting from 2025-10-17",
        "New York for the weekend with a $1500 budget",
        "Show me things to do in London this week",
        "Plan a trip to Boston in November"
    ]
    for q in test_queries:
        logger.info(f"Testing query: {q}")
        print(extract_entities(q))