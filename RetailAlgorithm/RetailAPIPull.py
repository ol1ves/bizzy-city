import requests
import time
import math

# ── Configuration ─────────────────────────────────────────────────────────────
GOOGLE_API_KEY = "x"  # Replace with your key

# Combined and cleaned list based on your requirements
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
    except:
        return []


def analyze_google_sentiment(place):
    reviews = place.get("reviews", [])
    if not reviews: return 0.0
    hits = sum(1 for r in reviews if any(k in r.get("text", {}).get("text", "").lower() for k in PAIN_KEYWORDS))
    return round(hits / len(reviews), 2)


# ── The Hub-Aware Scoring Logic ───────────────────────────────────────────────

def calculate_hub_aware_opportunity(data):
    rankings = []
    total_area_count = sum(len(items) for items in data.values())

    for cat, items in data.items():
        if not items: continue

        count = len(items)
        rated = [p for p in items if p.get("rating")]
        if not rated: continue

        # 1. Gather Metrics
        total_reviews = sum(p.get("userRatingCount", 0) for p in rated)
        avg_rating = sum(p['rating'] for p in rated) / len(rated)

        # ── SCALING FIX: Use Square Root of Rev/Loc ──
        # This prevents clothing_store (1159 revs) from being 10x higher than niche shops
        reviews_per_loc = math.sqrt(total_reviews / count)

        # 2. Hub Multiplier
        market_share = count / max(total_area_count, 1)
        hub_bonus = 1 + (market_share * 3)

        # 3. Quality Gap
        quality_gap = max(0.5, 4.8 - avg_rating)

        # 4. Friction (Analyze the 'best' store)
        top_place = sorted(rated, key=lambda x: x['rating'], reverse=True)[0]
        friction = analyze_google_sentiment(top_place)

        # ── PAIN WEIGHTING: Exponential ──
        # (1 + friction)^3 makes HIGH pain significantly more valuable than LOW pain
        pain_multiplier = math.pow(1 + friction, 3)

        # ── SATURATION PENALTY ──
        # If count is 20, we reduce the score because the physical space is full
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


# ── Updated Print Loop ───────────────────────────────────────────────────────
if __name__ == "__main__":
    LAT, LNG = 40.7150, -73.9967

    raw_market_data = {}
    print(f"🏙️  Scanning City Hub at {LAT}, {LNG}...")

    for category in CATEGORIES:
        results = search_nearby_retail(LAT, LNG, category)
        raw_market_data[category] = results
        print(f"  ✓ {category:<22} | Found: {len(results)}")
        time.sleep(0.05)

    final_rankings = calculate_hub_aware_opportunity(raw_market_data)

    if not final_rankings:
        print("\n❌ No rankings could be generated. Ensure your Place results contain 'rating' or 'userRatingCount'.")
    else:
        print("\n" + "═" * 105)
        print(f"{'RANK':<5} {'CATEGORY':<22} {'SCORE':<10} {'REV/LOC':<10} {'ESTAB.':<8} {'SHARE':<10} {'PAIN'}")
        print("─" * 105)

        for i, res in enumerate(final_rankings[:25], 1):
            pain_lvl = "HIGH" if res['friction'] > 0.2 else "MED" if res['friction'] > 0.05 else "LOW"
            print(
                f"{i:<5} {res['category']:<22} {res['score']:<10.1f} {res['rev_per_loc']:<10} {res['count']:<8} {res['share']:<10.1%} {pain_lvl}")