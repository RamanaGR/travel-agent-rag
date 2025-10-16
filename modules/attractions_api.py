import requests
import os
import json
import logging
from modules.rag_engine import RAGEngine
from config.config import RAPIDAPI_KEY, RAPIDAPI_HOST, CACHE_FILE, COUNTER_FILE, GEOID_CACHE_FILE

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

# ---------- Counter Helpers ----------
def _get_api_count():
    logger.debug(f"Reading API counter from {COUNTER_FILE}")
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r") as f:
                count = int(f.read().strip())
                logger.debug(f"API counter value: {count}")
                return count
        except ValueError as e:
            logger.error(f"❌ Failed to parse API counter: {e}")
            return 0
    logger.debug(f"Counter file {COUNTER_FILE} does not exist")
    return 0

def _increment_api_counter():
    logger.debug(f"Incrementing API counter in {COUNTER_FILE}")
    try:
        os.makedirs("data", exist_ok=True)
        count = _get_api_count() + 1
        with open(COUNTER_FILE, "w") as f:
            f.write(str(count))
        logger.debug(f"API counter incremented to {count}")
        return count
    except Exception as e:
        logger.error(f"❌ Error incrementing API counter: {e}")
        return _get_api_count()

# ---------- Cache Helpers ----------
def _load_cache(file_path):
    logger.debug(f"Loading cache from {file_path}")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                content = f.read().strip()
                if not content:
                    logger.warning(f"⚠️ Cache file {file_path} is empty")
                    return {}
                cache = json.loads(content)
                logger.debug(f"Cache loaded successfully from {file_path}")
                return cache
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse cache file {file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ Error loading cache file {file_path}: {e}")
            return {}
    logger.debug(f"Cache file {file_path} does not exist")
    return {}

def _save_cache(file_path, data):
    logger.debug(f"Saving cache to {file_path}")
    try:
        os.makedirs("data", exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)
        logger.info(f"✅ Cache saved to {file_path}")
    except Exception as e:
        logger.error(f"❌ Error saving cache to {file_path}: {e}")

# ======================================================
# ============== GEO ID FETCH & CACHE ==================
# ======================================================
def get_geo_id(city: str):
    """Fetch and cache the TripAdvisor geoId for a given city."""
    logger.info(f"⚡ Fetching geoId for {city}")
    geo_cache = _load_cache(GEOID_CACHE_FILE)

    # --- Step 1: Return from cache if exists ---
    if city in geo_cache:
        logger.info(f"✅ Using cached geoId for {city}: {geo_cache[city]}")
        return geo_cache[city]

    # --- Step 2: Live API Call ---
    url = f"https://{RAPIDAPI_HOST}/locations/v2/search"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type": "application/json",
    }
    payload = {"query": city, "updateToken": ""}

    try:
        count = _increment_api_counter()
        logger.info(f"📊 RapidAPI call #{count} → locations/v2/search")
        if count > 480:
            logger.warning(f"⚠️ Approaching monthly RapidAPI quota! Avoiding further live calls.")
            return None

        logger.debug(f"Making API request to {url}")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.error(f"❌ Failed to get geoId ({response.status_code}): {response.text}")
            return None

        data = response.json()
        logger.debug(f"API response received for geoId search")
        results = (
            data.get("data", {})
            .get("AppPresentation_queryAppSearch", {})
            .get("sections", [])
        )

        if not results:
            logger.warning(f"⚠️ No results found for city: {city}")
            return None

        geo_id = None
        for item in results:
            logger.debug(f"Processing item for geoId: {item.get('__typename', 'N/A')}")
            geo_id = find_first_numeric_geoid(item)
            if geo_id is not None and geo_id != "":
                break

        if not geo_id:
            logger.warning(f"⚠️ No geoId found for {city}")
            return None

        # Cache and return
        geo_cache[city] = geo_id
        _save_cache(GEOID_CACHE_FILE, geo_cache)
        logger.info(f"✅ Found and cached geoId {geo_id} for city: {city}")
        return geo_id

    except Exception as e:
        logger.error(f"❌ Error fetching geoId for {city}: {e}")
        return None

def find_first_numeric_geoid(data):
    logger.debug("Searching for numeric geoId")
    if isinstance(data, dict):
        if 'geoId' in data:
            value = data['geoId']
            if value is not None:
                try:
                    geo_id = int(value)
                    logger.debug(f"Found numeric geoId: {geo_id}")
                    return geo_id
                except ValueError:
                    logger.debug(f"Skipping non-numeric geoId: {value}")
                    pass
        for value in data.values():
            result = find_first_numeric_geoid(value)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_first_numeric_geoid(item)
            if result is not None:
                return result
    logger.debug("No numeric geoId found")
    return None

# ======================================================
# =============== ATTRACTIONS FETCH ====================
# ======================================================
def fetch_attractions(city: str, limit: int = 10):
    """Fetch and cache top attractions for a given city."""
    logger.info(f"⚡ Fetching attractions for {city}")
    cache = {}#_load_cache(CACHE_FILE)
    if city in cache:
        logger.info(f"✅ Using cached attractions for {city}")
        return cache[city]

    geo_id = get_geo_id(city)
    if not geo_id:
        logger.warning(f"⚠️ Could not fetch attractions for {city} (missing geoId). Using cached data if available.")
        return cache.get(city, [{"name": "No attractions found", "description": "N/A"}])

    url = f"https://{RAPIDAPI_HOST}/attractions/v2/list"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type": "application/json",
    }

    payload = {
        "geoId": geo_id,
        "pax": [{"ageBand": "ADULT", "count": 2}],
        "sort": "TRAVELER_RANKED",
        "sortOrder": "desc",
        "filters": [
            {"id": "category", "value": ["47","48","52","40", "59", "49", "57", "20"]}
        ],
        "updateToken": ""
    }

    try:
        count = _increment_api_counter()
        logger.info(f"📊 RapidAPI call #{count} → attractions/v2/list")
        if count > 480:
            logger.warning(f"⚠️ Approaching monthly RapidAPI quota! Returning cached data.")
            return cache.get(city, [{"name": "No attractions found", "description": "N/A"}])

        logger.debug(f"Making API request to {url}")
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code != 200:
            logger.error(f"❌ Error fetching attractions: Status Code {response.status_code}, Response: {response.text}")
            return [{"name": "No attractions found", "description": "N/A"}]

        data = response.json()
        logger.debug(f"API response received for attractions")
        attractions = parse_attractions_from_response(data, limit=limit)
        logger.debug(f"Parsed {len(attractions)} attractions")

        if not attractions:
            logger.warning(f"⚠️ No attractions found for {city}")
            attractions = [{"name": "No attractions found", "description": "N/A"}]
        else:
            attractions = attractions[:limit]

        logger.info(f"🆕 New city detected: {city}. Caching data.")
        # updated_cache = _load_cache(CACHE_FILE)
        # updated_cache[city] = attractions
        # _save_cache(CACHE_FILE, updated_cache)

        logger.info(f"✅ Fetched and cached {len(attractions)} attractions for {city}")
        return attractions

    except Exception as e:
        logger.error(f"❌ Error fetching attractions for {city}: {e}")
        return [{"name": "No attractions found", "description": "N/A"}]

def parse_attractions_from_response(resp_json, limit=10):
    """
    Universal parser for TripAdvisor attractions responses.
    Returns a list of normalized attraction dicts with fields:
      name, description, category, rating, reviews, photo, link
    Works across multiple response shapes.
    """
    logger.debug("Parsing attractions from API response")
    out = []

    def safe(d, *keys, default=None):
        cur = d
        for k in keys:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                return default
        return cur

    def normalize_card(card):
        logger.debug(f"Normalizing card: {safe(card, 'cardTitle', 'string') or safe(card, 'title') or 'Unknown'}")
        name = (
            safe(card, "cardTitle", "string")
            or safe(card, "title")
            or safe(card, "name")
            or safe(card, "localizedName")
            or safe(card, "title", "string")
        ) or "Unknown"

        rating = safe(card, "bubbleRating", "rating") or safe(card, "rating") or "N/A"
        reviews = safe(card, "bubbleRating", "numberReviews", "string") or safe(card, "reviewCount") or ""
        if isinstance(reviews, str):
            reviews = reviews.replace("(", "").replace(")", "").strip()

        category = safe(card, "primaryInfo", "text") or safe(card, "category", "name") or safe(card, "category") or "N/A"

        # Updated image parsing for larger images
        photo_sizes = safe(card, "cardPhoto", "sizes") or safe(card, "photo", "sizes") or {}
        photo = photo_sizes.get("large", {}).get("url") or photo_sizes.get("medium", {}).get("url") or photo_sizes.get("small", {}).get("url") or ""
        if not photo:
            url_template = safe(card, "cardPhoto", "sizes", "urlTemplate") or safe(card, "cardPhoto", "photo", "url") or safe(card, "photo", "url") or ""
            if url_template and "{width}" in url_template:
                photo = url_template.replace("{width}", "400").replace("{height}", "300")

        route = safe(card, "cardLink", "route")
        if isinstance(route, dict):
            url_part = route.get("url") or route.get("nonCanonicalUrl") or ""
            link = "https://www.tripadvisor.com" + url_part if url_part else ""
        else:
            link = safe(card, "detailPageUrl") or safe(card, "cardLink", "url") or ""

        desc = safe(card, "descriptiveText", "text") or safe(card, "content", "description") or safe(card, "snippet") or ""

        return {
            "name": name,
            "description": desc or "N/A",
            "category": category,
            "rating": rating,
            "reviews": reviews,
            "photo": photo,
            "link": link,
        }

    try:
        data = resp_json.get("data", {})
        app_list = data.get("AppPresentation_queryAppListV2") or data.get("AppPresentation_queryAppListV2", [])
        if app_list and isinstance(app_list, list):
            first = app_list[0] if app_list else {}
            sections = first.get("sections") or []
            for sec in sections:
                if isinstance(sec, dict):
                    items = sec.get("items") or sec.get("list", []) or sec.get("cardItems") or []
                    if items and isinstance(items, list):
                        for item in items:
                            card = item.get("listSingleCardContent") or item.get("appSearchCardContent") or item
                            out.append(normalize_card(card))
                    else:
                        card = sec.get("listSingleCardContent") or sec
                        out.append(normalize_card(card))
        if not out:
            sections2 = data.get("sections") or data.get("results") or []
            if isinstance(sections2, list):
                for block in sections2:
                    if isinstance(block, dict):
                        items = block.get("items") or block.get("cards") or block.get("list") or []
                        if isinstance(items, list) and items:
                            for it in items:
                                card = it.get("listSingleCardContent") or it.get("appSearchCardContent") or it
                                out.append(normalize_card(card))
                        else:
                            card = block.get("listSingleCardContent") or block
                            out.append(normalize_card(card))

        if not out:
            def scan_for_cards(obj):
                if isinstance(obj, dict):
                    if any(k in obj for k in ("cardTitle", "cardPhoto", "bubbleRating", "listSingleCardContent")):
                        card = obj.get("listSingleCardContent") or obj
                        out.append(normalize_card(card))
                        return
                    for v in obj.values():
                        scan_for_cards(v)
                elif isinstance(obj, list):
                    for i in obj:
                        scan_for_cards(i)
            scan_for_cards(resp_json)

    except Exception as e:
        logger.error(f"❌ parse_attractions_from_response error: {e}")

    seen = set()
    cleaned = []
    for a in out:
        name = a.get("name") or ""
        key = (name.strip().lower(), a.get("link") or "")
        if name and key not in seen:
            seen.add(key)
            cleaned.append(a)
        if len(cleaned) >= limit:
            break

    logger.info(f"✅ Parsed {len(cleaned)} unique attractions")
    return cleaned

# ======================================================
# =============== CACHE RETRIEVAL ======================
# ======================================================
def get_cached_attractions(city: str):
    logger.info(f"⚡ Retrieving cached attractions for {city}")
    cache = _load_cache(CACHE_FILE)
    attractions = cache.get(city, [])
    logger.info(f"✅ Retrieved {len(attractions)} cached attractions for {city}")
    return attractions