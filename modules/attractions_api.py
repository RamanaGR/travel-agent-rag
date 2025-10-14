import requests
import os
from modules.rag_engine import RAGEngine
from config.config import RAPIDAPI_KEY, RAPIDAPI_HOST, CACHE_FILE, COUNTER_FILE, GEOID_CACHE_FILE

# ---------- Counter Helpers ----------
def _get_api_count():
    if os.path.exists(COUNTER_FILE):
        try:
            with open(COUNTER_FILE, "r") as f:
                return int(f.read().strip())
        except ValueError:
            return 0
    return 0


def _increment_api_counter():
    os.makedirs("data", exist_ok=True)
    count = _get_api_count() + 1
    with open(COUNTER_FILE, "w") as f:
        f.write(str(count))
    return count


# ---------- Cache Helpers ----------
def _load_cache(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return {}


def _save_cache(file_path, data):
    os.makedirs("data", exist_ok=True)
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)


# ======================================================
# ============== GEO ID FETCH & CACHE ==================
# ======================================================
def get_geo_id(city: str):
    """Fetch and cache the TripAdvisor geoId for a given city."""
    geo_cache = _load_cache(GEOID_CACHE_FILE)

    # --- Step 1: Return from cache if exists ---
    if city in geo_cache:
        print(f"✅ Using cached geoId for {city}: {geo_cache[city]}")
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
        print(f"📊 RapidAPI call #{count} → locations/v2/search")
        if count > 480:
            print("⚠️ Approaching monthly RapidAPI quota! Avoiding further live calls.")
            return None

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ Failed to get geoId ({response.status_code}): {response.text}")
            return None

        data = response.json()
        # import json
        # data = json.load(open('response.json'))
        print(data)
        results = (
            data.get("data", {})
            .get("AppPresentation_queryAppSearch", {})
            .get("sections", [])
        )

        if not results:
            print(f"⚠️ No results found for city: {city}")
            return None

        geo_id = None
        for item in results:
            print(item)
            geo_id = find_first_numeric_geoid(item)
          #  details = item.get("singleCardContent", {}).get("cardLink", {}).get("route", {}).get("typedParams", {})
          #  details = d if 'geoId' in data return data['geoId']
          #   print(details)
            if geo_id is not None and geo_id != "":
                break

        if not geo_id:
            print(f"⚠️ No geoid found in any result for {city}")
            return None

        # Cache and return
        geo_cache[city] = geo_id
        _save_cache(GEOID_CACHE_FILE, geo_cache)

        print(f"✅ Found geoId {geo_id} for city: {city}")
        return geo_id

    except Exception as e:
        print(f"⚠️ Error fetching geoId: {e}")
        return None

import json

def find_first_numeric_geoid(data):
    """
    Recursively searches for the 'geoId' key in a nested dictionary or list
    and returns the first integer value found. Skips None or non-numeric values.
    """
    if isinstance(data, dict):
        if 'geoId' in data:
            value = data['geoId']
            if value is not None:
                try:
                    return int(value)
                except ValueError:
                    pass  # Continue searching if not convertible to int
        for value in data.values():
            result = find_first_numeric_geoid(value)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_first_numeric_geoid(item)
            if result is not None:
                return result
    return None



# ======================================================
# =============== ATTRACTIONS FETCH ====================
# ======================================================
def fetch_attractions(city: str, limit: int = 10):
    """Fetch and cache top attractions for a given city."""
    cache = _load_cache(CACHE_FILE)
    if city in cache:
        print(f"✅ Using cached attractions for {city}")
        return cache[city]

    geo_id = get_geo_id(city)
    if not geo_id:
        print("⚠️ Could not fetch attractions (missing geoId). Using cached data if available.")
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
            {"id": "category", "value": ["47","48","52","40", "59", "49", "57", "20"]},
            {"id": "rating", "value": ["4.0"]}  # Only 4+ star attractions
        ],
        "updateToken": ""
    }

    try:
        count = _increment_api_counter()
        print(f"📊 RapidAPI call #{count} → attractions/v2/list")
        if count > 480:
            print("⚠️ Approaching monthly RapidAPI quota! Returning cached data only.")
            return cache.get(city, [{"name": "No attractions found", "description": "N/A"}])

        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"⚠️ Error fetching attractions: {response.status_code}")
            return [{"name": "No attractions found", "description": "N/A"}]

        data = response.json()
        # --- Inline Parser ---
        attractions = []

        # data = json.load(open('att_response.json'))
        attractions = parse_attractions_from_response(data)
        print(data)

        if not attractions:
            attractions = [{"name": "No attractions found", "description": "N/A"}]
        else:
            attractions = attractions[:limit]

        # FIX: Remove the RAG Index Rebuild block to prevent timeouts.
        # The rag_engine is now 'self-healing' and will rebuild the index
        # when search_attractions is called if the data is new/missing.
        if city not in open(CACHE_FILE).read():
            print(f"🆕 New city detected: {city}. Caching data.")
            updated_cache = _load_cache(CACHE_FILE)
            updated_cache[city] = attractions
            _save_cache(CACHE_FILE, updated_cache)

        print(f"✅ Fetched and cached {len(attractions)} attractions for {city}")

        return attractions

    except Exception as e:
        print(f"⚠️ Error fetching attractions: {e}")
        return [{"name": "No attractions found", "description": "N/A"}]


def parse_attractions_from_response(resp_json, limit=10):
    """
    Universal parser for TripAdvisor attractions responses.
    Returns a list of normalized attraction dicts with fields:
      name, description, category, rating, reviews, photo, link
    Works across multiple response shapes.
    """
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
        # card may be 'listSingleCardContent', 'appSearchCardContent', direct item, etc.
        # Try multiple patterns
        name = (
            safe(card, "cardTitle", "string")
            or safe(card, "title")
            or safe(card, "name")
            or safe(card, "localizedName")
            or safe(card, "title", "string")
        ) or "Unknown"

        # rating: can be bubbleRating.rating or rating
        rating = safe(card, "bubbleRating", "rating") or safe(card, "rating") or "N/A"

        # reviews: bubbleRating.numberReviews.string may have parentheses
        reviews = safe(card, "bubbleRating", "numberReviews", "string") or safe(card, "reviewCount") or ""
        if isinstance(reviews, str):
            reviews = reviews.replace("(", "").replace(")", "").strip()

        # category or primaryInfo.text
        category = safe(card, "primaryInfo", "text") or safe(card, "category", "name") or safe(card, "category") or "N/A"

        # photo: urlTemplate needs width/height replacement
        url_template = safe(card, "cardPhoto", "sizes", "urlTemplate") or safe(card, "cardPhoto", "photo", "url") or safe(card, "photo", "url") or ""
        if url_template and "{width}" in url_template:
            photo = url_template.replace("{width}", "400").replace("{height}", "300")
        else:
            photo = url_template

        # link: internal route or detail url
        route = safe(card, "cardLink", "route")
        if isinstance(route, dict):
            url_part = route.get("url") or route.get("nonCanonicalUrl") or ""
            link = "https://www.tripadvisor.com" + url_part if url_part else ""
        else:
            link = safe(card, "detailPageUrl") or safe(card, "cardLink", "url") or ""

        # description: descriptiveText / content / primary snippet
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

    # 1) Common case: nested under data -> AppPresentation_queryAppListV2 -> [0] -> sections -> items / listSingleCardContent
    try:
        data = resp_json.get("data", {})
        app_list = data.get("AppPresentation_queryAppListV2") or data.get("AppPresentation_queryAppListV2", [])
        if app_list and isinstance(app_list, list):
            first = app_list[0] if app_list else {}
            sections = first.get("sections") or []
            for sec in sections:
                # items can be in 'items' or 'listSingleCardContent' etc.
                if isinstance(sec, dict):
                    # items list
                    items = sec.get("items") or sec.get("list", []) or sec.get("cardItems") or []
                    if items and isinstance(items, list):
                        for item in items:
                            # item may wrap 'listSingleCardContent'
                            card = item.get("listSingleCardContent") or item.get("appSearchCardContent") or item
                            out.append(normalize_card(card))
                    else:
                        # section itself might be a card
                        card = sec.get("listSingleCardContent") or sec
                        out.append(normalize_card(card))
        # 2) Fallback: some responses put cards at data['sections'] or data['results']
        if not out:
            # try data -> sections top-level
            sections2 = data.get("sections") or data.get("results") or []
            if isinstance(sections2, list):
                for block in sections2:
                    # block may be an object containing card list
                    if isinstance(block, dict):
                        # try common places
                        items = block.get("items") or block.get("cards") or block.get("list") or []
                        if isinstance(items, list) and items:
                            for it in items:
                                card = it.get("listSingleCardContent") or it.get("appSearchCardContent") or it
                                out.append(normalize_card(card))
                        else:
                            # single dict card
                            card = block.get("listSingleCardContent") or block
                            out.append(normalize_card(card))

        # 3) Final fallback: scan entire JSON for objects that look like cards (heuristic)
        if not out:
            def scan_for_cards(obj):
                if isinstance(obj, dict):
                    # heuristics: presence of cardTitle or cardPhoto or bubbleRating
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
        print(f"⚠️ parse_attractions_from_response error: {e}")

    # Remove duplicates and empty names, preserve order
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

    return cleaned



# ======================================================
# =============== CACHE RETRIEVAL ======================
# ======================================================
def get_cached_attractions(city: str):
    cache = _load_cache(CACHE_FILE)
    return cache.get(city, [])
