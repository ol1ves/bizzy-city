import requests
import time
import math
import os
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# ── Configuration ─────────────────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

CATEGORIES = [
    "chiropractor", "dental_clinic", "dentist", "doctor", "drugstore", "hospital",
    "massage", "physiotherapist", "sauna", "skin_care_clinic", "spa", "tanning_studio",
    "wellness_center", "yoga_studio", "apartment_building", "hotel", "motel",
    "barber_shop", "beauty_salon", "clothing_store", "department_store",
    "electronics_store", "furniture_store", "grocery_store", "jewelry_store",
    "pet_store", "shopping_mall", "supermarket", "gift_shop", "book_store"
]

PAIN_KEYWORDS = ["rude", "dirty", "expensive", "slow", "wait", "appointment", "crowded", "line"]
TIMEOUT = 10


# ── Google Places Logic ───────────────────────────────────────────────────────

def search_nearby_retail(lat, lng, category, radius=1000):
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.rating,places.userRatingCount,places.reviews"
    }
    body = {
        "includedTypes": [category],
        "maxResultCount": 20,
        "locationRestriction": {
            "circle": {"center": {"latitude": lat, "longitude": lng}, "radius": radius}
        }
    }
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=TIMEOUT)
        return resp.json().get("places", []) if resp.status_code == 200 else []
    except Exception:
        return []


def analyze_google_sentiment(place):
    reviews = place.get("reviews", [])
    if not reviews:
        return 0.0
    hits = sum(1 for r in reviews if any(k in r.get("text", {}).get("text", "").lower() for k in PAIN_KEYWORDS))
    return round(hits / len(reviews), 2)


# ── The Hub-Aware Scoring Logic ───────────────────────────────────────────────

def calculate_hub_aware_opportunity(data):
    rankings = []
    total_area_count = sum(len(items) for items in data.values())

    for cat, items in data.items():
        if not items:
            continue

        count = len(items)
        rated = [p for p in items if p.get("rating")]
        if not rated:
            continue

        total_reviews = sum(p.get("userRatingCount", 0) for p in rated)
        avg_rating = sum(p['rating'] for p in rated) / len(rated)

        # sqrt scaling prevents high-review categories from dominating
        reviews_per_loc = math.sqrt(total_reviews / count)

        market_share = count / max(total_area_count, 1)
        hub_bonus = 1 + (market_share * 3)

        quality_gap = max(0.5, 4.8 - avg_rating)

        top_place = sorted(rated, key=lambda x: x['rating'], reverse=True)[0]
        friction = analyze_google_sentiment(top_place)

        pain_multiplier = math.pow(1 + friction, 3)

        saturation_penalty = 0.5 if count >= 20 else 1.0

        # ── THE NEW FORMULA ──
        score = (reviews_per_loc * (quality_gap ** 2) * hub_bonus * pain_multiplier * saturation_penalty) / math.log10(
            count + 1)

        rankings.append({
            "category": cat,
            "score": round(score, 2),
            "avg_rating": round(avg_rating, 1),
            "count": count,
            "share": market_share,
            "rev_per_loc": round(total_reviews / count, 1),
            "friction": friction
        })

    return sorted(rankings, key=lambda x: x["score"], reverse=True)
