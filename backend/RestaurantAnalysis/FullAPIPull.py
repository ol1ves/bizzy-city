import requests
import time
import math
import os
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# ── Configuration ─────────────────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

CATEGORIES = [
    "acai_shop", "american_restaurant", "asian_fusion_restaurant", "asian_restaurant",
    "bagel_shop", "bakery", "bar", "barbecue_restaurant", "bistro", "breakfast_restaurant",
    "brewery", "british_restaurant", "brunch_restaurant", "burger_restaurant", "cafe",
    "chicken_wings_restaurant", "chinese_restaurant", "coffee_shop", "cocktail_bar",
    "dessert_shop", "diner", "french_restaurant", "greek_restaurant", "indian_restaurant",
    "italian_restaurant", "japanese_restaurant", "mexican_restaurant", "pizza_restaurant",
    "seafood_restaurant", "steak_house", "sushi_restaurant", "thai_restaurant",
    "vegan_restaurant", "vietnamese_restaurant", "wine_bar"
]

WAIT_KEYWORDS = ["wait", "line", "packed", "busy", "crowded", "hour"]
COMPLAINT_KEYWORDS = ["never", "awful", "terrible", "worst", "rude", "disgusting", "avoid"]
UNMET_KEYWORDS = ["wish", "needs more", "only one", "no other", "nowhere else"]
TIMEOUT = 10
MIN_REVIEWS = 10


# ── Google Places Logic ───────────────────────────────────────────────────────

def search_category(lat, lng, category, radius=200):
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.rating,places.userRatingCount,places.formattedAddress,places.location"
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


def scrape_area(lat, lng, radius=200):
    results = {}
    all_seen_ids = set()  # Track total unique businesses in area
    print(f"🔍 Scanning {len(CATEGORIES)} categories in {radius}m...")

    for category in CATEGORIES:
        places = search_category(lat, lng, category, radius)
        for p in places:
            if p.get("id"): all_seen_ids.add(p["id"])

        if not places:
            results[category] = {"count": 0, "top_place": None, "places": []}
            continue

        rated = [p for p in places if p.get("rating") and (p.get("userRatingCount") or 0) >= MIN_REVIEWS]
        if not rated:
            results[category] = {"count": len(places), "top_place": None, "places": places}
            continue

        sorted_p = sorted(rated, key=lambda x: (x['rating'], x['userRatingCount']), reverse=True)
        top = sorted_p[0]
        avg = sum(p['rating'] for p in sorted_p) / len(sorted_p)

        results[category] = {
            "count": len(places),
            "top_place": top["displayName"]["text"],
            "top_place_id": top.get("id"),
            "top_place_address": top.get("formattedAddress", ""),
            "top_rating": top.get("rating"),
            "top_review_count": top.get("userRatingCount", 0),
            "avg_rating": round(avg, 2),
            "places": places,
        }
        print(f"  ✓ {category:<25} | {len(places)} found | Top: {results[category]['top_place']}")
        time.sleep(0.05)

    return results, len(all_seen_ids)


def opportunity_score(data):
    scores = []
    seen = set()
    for cat, d in data.items():
        if d.get("count", 0) == 0 or not d.get("top_place"):
            continue
        if d["top_place_id"] in seen: continue
        seen.add(d["top_place_id"])

        rev_count = d["top_review_count"] or 0
        gap = 5.0 - (d["avg_rating"] or 3.0)
        score = (rev_count * gap) / max(d["count"], 1)
        scores.append((cat, score, d))
    return sorted(scores, key=lambda x: x[1], reverse=True)


# ── Yelp/SerpApi Logic ────────────────────────────────────────────────────────

def serpapi_get(params):
    params["api_key"] = SERPAPI_KEY
    try:
        resp = requests.get("https://serpapi.com/search", params=params, timeout=TIMEOUT)
        return resp.json() if resp.status_code == 200 else {}
    except Exception:
        return {}


def get_yelp_place_id(name, address):
    data = serpapi_get({"engine": "yelp", "find_desc": name, "find_loc": address})
    results = data.get("organic_results", [])
    if results:
        biz = results[0]
        return (biz.get("place_ids", [None])[0], biz)
    return None, None


def get_yelp_reviews(place_id, max_pages=1):
    reviews = []
    for page in range(max_pages):
        data = serpapi_get({"engine": "yelp_reviews", "place_id": place_id, "start": page * 50})
        reviews.extend(data.get("reviews", []))
    return reviews


def analyze_reviews(reviews):
    waits = complaints = low_stars = 0
    total = len(reviews) or 1
    for r in reviews:
        text = r.get("comment", {}).get("text", "").lower()
        star = r.get("rating", 5)
        if any(k in text for k in WAIT_KEYWORDS): waits += 1
        if any(k in text for k in COMPLAINT_KEYWORDS): complaints += 1
        if star <= 2: low_stars += 1

    return {
        "total_reviews_sampled": total,
        "complaint_rate": round(max(complaints, low_stars) / total, 2),
        "wait_rate": round(waits / total, 2)
    }


def calculate_hybrid_score(category_name, current_place_data, all_google_data, yelp_analysis,
                           total_area_establishments):
    count = current_place_data["count"]
    top_reviews = current_place_data["top_review_count"]

    # 1. Quality Gap: 5.0 minus the top rating.
    # Even a 4.8 has a 0.2 gap. This prevents "Zero Scores".
    avg_rating = current_place_data["top_rating"] or 0
    quality_gap = max(0.1, 5.0 - avg_rating)

    # 2. Market Hub Logic:
    # We want categories that people actually GO to this area for.
    # We sum the review counts of the top place in this category.
    demand_volume = top_reviews

    # 3. Density Bonus:
    # In Chinatown, if there are 20 Chinese restaurants, it's a HUB.
    # We reward density because it proves foot traffic.
    market_density_bonus = math.log10(count + 1)

    # 4. Ghost Town Penalty:
    # If there are < 3 places, it might not be a fit for this specific neighborhood.
    fit_modifier = 0.5 if count < 3 else 1.2

    # 5. Friction (Pain Points) from Yelp
    friction = 1.0
    if yelp_analysis:
        friction += (yelp_analysis["wait_rate"] * 2.5)  # Waits are a huge opportunity
        friction += (yelp_analysis["complaint_rate"] * 3.5)  # Bad service/quality is a huge opportunity

    # Final Calculation
    score = (demand_volume * quality_gap * friction * market_density_bonus * fit_modifier)

    market_share = count / max(total_area_establishments, 1)
    return round(score, 2), market_share


def enrich_and_rank(ranked, google_data, total_establishments, top_n=15):
    print(f"\n🔍 Deep-diving top {top_n} via Yelp (Market Size: {total_establishments})...")
    final = []
    for cat, initial_score, d in ranked[:top_n]:
        # Yelp Scrape
        y_id, biz = get_yelp_place_id(d["top_place"], d["top_place_address"])
        analysis = None
        if y_id:
            revs = get_yelp_reviews(y_id)
            analysis = analyze_reviews(revs)
            analysis["yelp_rating"] = biz.get("rating", "N/A")

        h_score, m_share = calculate_hybrid_score(cat, d, google_data, analysis, total_establishments)

        final.append({"cat": cat, "score": h_score, "share": m_share, "g": d, "y": analysis})
        print(f"  {'✓' if y_id else '✗'} {cat:<25} | Score: {h_score:,.1f}")

    return sorted(final, key=lambda x: x["score"], reverse=True)

"""
# ── Update your Main block call ──────────────────────────────────────────────
if __name__ == "__main__":
    LAT, LNG = 40.7258,-73.9932

    google_data, total_found = scrape_area(LAT, LNG)
    initial_ranked = opportunity_score(google_data)

    # NOTE: We now pass 'google_data' as the second argument here
    final_ranked = enrich_and_rank(initial_ranked, google_data, total_found, top_n=15)

    print(f"\n\n🏆 FINAL HYBRID RANKINGS\n" + "═" * 105)
    print(f"{'Rank':<5} {'Category':<22} {'Score':<8} {'Share':<8} {'G-Star':<8} {'Y-Star':<8} {'Pain Points'}")
    print("─" * 105)
    for i, res in enumerate(final_ranked, 1):
        # Default to LOW
        pains = []
        pain_level = "LOW"

        if res['y']:
            complaint_rate = res['y'].get('complaint_rate', 0)
            wait_rate = res['y'].get('wait_rate', 0)

            # 1. HIGH PAIN: Poor quality is a severe market gap
            if complaint_rate > 0.18:
                pain_level = "HIGH"

            # 2. MED PAIN: High wait times with decent quality
            # (Only set to MED if it wasn't already set to HIGH by complaints)
            elif wait_rate > 0.12:
                pain_level = "MED"

        # Store the result back into the object for the printer
        pains.append(pain_level)

        print(
            f"{i:<5} {res['cat']:<22} {res['score']:<8.1f} {res['share']:<8.1%} {res['g']['top_rating']:<8} {res['y']['yelp_rating'] if res['y'] else 'N/A':<8} {', '.join(pains) if pains else '-'}")
            """