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

def search_nearby_retail(lat, lng, category, radius=200):
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
    except:
        return []


def analyze_google_sentiment(place):
    reviews = place.get("reviews", [])
    if not reviews: return 0.0

    # 1. Textual Hits (Your existing logic)
    text_hits = sum(1 for r in reviews if any(
        k in r.get("text", {}).get("text", "").lower() for k in PAIN_KEYWORDS
    ))

    # 2. Implicit Pain (Low star ratings in recent reviews)
    # We treat 1 and 2-star reviews as high-friction signals even without keywords
    low_stars = sum(1 for r in reviews if r.get("rating", 5) <= 2)

    # 3. Weighted Friction Score
    # We take the union of text hits and low stars to ensure we don't double-count
    # but capture the essence of the "bad experience."
    total_friction_signals = max(text_hits, low_stars)

    return round(total_friction_signals / len(reviews), 2)

# ── The Hub-Aware Scoring Logic ───────────────────────────────────────────────

def calculate_hub_aware_opportunity(data):
    rankings = []
    total_area_count = sum(len(items) for items in data.values())

    for cat, items in data.items():
        rated = [p for p in items if p.get("rating") and p.get("userRatingCount") is not None]
        count = len(items)
        if not rated or count == 0: continue

        # 1. Metrics
        total_reviews = sum(p.get("userRatingCount", 0) for p in rated)
        avg_rating = sum(p['rating'] for p in rated) / len(rated)

        # Dampen the effect of massive review counts
        reviews_per_loc_scaled = math.sqrt(total_reviews / count)

        # 2. Quality Gap (Targeting 4.7 as the 'gold standard')
        # Squaring this makes 'bad' areas stand out exponentially
        quality_gap = max(0.7, 4.7 - avg_rating)

        # 3. Sentiment Friction
        top_place = max(rated, key=lambda x: x['rating'])
        friction = analyze_google_sentiment(top_place)
        pain_multiplier = math.pow(1 + friction, 2.5)  # Slightly lower exponent to avoid total blowout

        # 4. Competition & Saturation
        # log10(count + 1.1) ensures we don't divide by zero and smooths the competition penalty
        comp_penalty = math.log10(count + 1.1)

        # Hard wall for physical saturation
        saturation_multiplier = 0.5 if count >= 20 else 1.0

        # ── THE FORMULA ──
        # We want high reviews, high gap, and high pain, but LOW competition count
        score = (reviews_per_loc_scaled * (quality_gap ** 2) * pain_multiplier * saturation_multiplier) / comp_penalty

        rankings.append({
            "category": cat,
            "score": round(score, 2),
            "avg_rating": round(avg_rating, 1),
            "count": count,
            "rev_per_loc": round(total_reviews / count, 1),
            "friction": friction,
            "share": count / max(total_area_count, 1),
        })

    return sorted(rankings, key=lambda x: x["score"], reverse=True)
