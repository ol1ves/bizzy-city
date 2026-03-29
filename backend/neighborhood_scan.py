"""
neighborhood_scan.py
────────────────────
Builds the structured JSONB representation of a property's neighborhood scan
from raw Google Places, Yelp, and foot traffic data.

The output is a list of CategoryScan dicts, serialized to JSON and stored in
properties.neighborhood_scan for consumption by the ML model via get_ml_input().
"""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Optional

import pandas as pd

from FootTraffic.pckl import get_traffic_by_coords
from ml_interface import CategoryScan, FootTraffic, NearbyBusiness


# ── Category Mapping ─────────────────────────────────────────────────────────

GPLACE_TO_SURVIVABILITY_CATEGORY = {
    # --- Food & Drink → Accommodation and food services ---
    "acai_shop": "accommodation_and_food_services",
    "american_restaurant": "accommodation_and_food_services",
    "asian_fusion_restaurant": "accommodation_and_food_services",
    "asian_restaurant": "accommodation_and_food_services",
    "bagel_shop": "accommodation_and_food_services",
    "bakery": "accommodation_and_food_services",
    "bar": "accommodation_and_food_services",
    "barbecue_restaurant": "accommodation_and_food_services",
    "bistro": "accommodation_and_food_services",
    "breakfast_restaurant": "accommodation_and_food_services",
    "brewery": "accommodation_and_food_services",
    "british_restaurant": "accommodation_and_food_services",
    "brunch_restaurant": "accommodation_and_food_services",
    "burger_restaurant": "accommodation_and_food_services",
    "cafe": "accommodation_and_food_services",
    "chicken_wings_restaurant": "accommodation_and_food_services",
    "chinese_restaurant": "accommodation_and_food_services",
    "coffee_shop": "accommodation_and_food_services",
    "cocktail_bar": "accommodation_and_food_services",
    "dessert_shop": "accommodation_and_food_services",
    "diner": "accommodation_and_food_services",
    "french_restaurant": "accommodation_and_food_services",
    "greek_restaurant": "accommodation_and_food_services",
    "indian_restaurant": "accommodation_and_food_services",
    "italian_restaurant": "accommodation_and_food_services",
    "japanese_restaurant": "accommodation_and_food_services",
    "mexican_restaurant": "accommodation_and_food_services",
    "pizza_restaurant": "accommodation_and_food_services",
    "seafood_restaurant": "accommodation_and_food_services",
    "steak_house": "accommodation_and_food_services",
    "sushi_restaurant": "accommodation_and_food_services",
    "thai_restaurant": "accommodation_and_food_services",
    "vegan_restaurant": "accommodation_and_food_services",
    "vietnamese_restaurant": "accommodation_and_food_services",
    "wine_bar": "accommodation_and_food_services",
    # --- Medical/Clinical → Health care and social assistance ---
    "chiropractor": "health_care_and_social_assistance",
    "dental_clinic": "health_care_and_social_assistance",
    "dentist": "health_care_and_social_assistance",
    "doctor": "health_care_and_social_assistance",
    "drugstore": "retail_trade",
    "hospital": "health_care_and_social_assistance",
    "physiotherapist": "health_care_and_social_assistance",
    # --- Personal care / Wellness → Other services ---
    "massage": "other_services",
    "sauna": "other_services",
    "skin_care_clinic": "other_services",
    "spa": "other_services",
    "tanning_studio": "other_services",
    "wellness_center": "other_services",
    "yoga_studio": "arts_entertainment_and_recreation",
    # --- Lodging → Accommodation and food services ---
    "hotel": "accommodation_and_food_services",
    "motel": "accommodation_and_food_services",
    # --- Real estate ---
    "apartment_building": "real_estate_and_rental_and_leasing",
    # --- Personal grooming → Other services ---
    "barber_shop": "other_services",
    "beauty_salon": "other_services",
    # --- Retail → Retail trade ---
    "clothing_store": "retail_trade",
    "department_store": "retail_trade",
    "electronics_store": "retail_trade",
    "furniture_store": "retail_trade",
    "grocery_store": "retail_trade",
    "jewelry_store": "retail_trade",
    "pet_store": "retail_trade",
    "shopping_mall": "retail_trade",
    "supermarket": "retail_trade",
    "gift_shop": "retail_trade",
    "book_store": "retail_trade",
}

_ZIP_RE = re.compile(r"\b(\d{5})\b")


# ── Helpers ──────────────────────────────────────────────────────────────────


def parse_zip_code(formatted_address: str) -> Optional[str]:
    """Extract the last 5-digit zip code from a Google Places formattedAddress."""
    matches = _ZIP_RE.findall(formatted_address)
    return matches[-1] if matches else None


def build_foot_traffic(lat: float, lng: float) -> FootTraffic:
    """Look up pedestrian traffic for a single lat/lng and return a FootTraffic."""
    result = get_traffic_by_coords(lat, lng)

    if isinstance(result, str) or not isinstance(result, pd.DataFrame) or result.empty:
        return FootTraffic()

    row = result.iloc[0]

    def _int_or_none(col):
        val = row.get(col)
        if val is not None and pd.notna(val):
            return int(val)
        return None

    def _float_or_none(col):
        val = row.get(col)
        if val is not None and pd.notna(val):
            return float(val)
        return None

    return FootTraffic(
        weekday_am=_int_or_none("predwkdyAM"),
        weekday_mid=_int_or_none("predwkdyMD"),
        weekday_pm=_int_or_none("predwkdyPM"),
        weekend_am=_int_or_none("predwkndAM"),
        weekend_mid=_int_or_none("predwkndMD"),
        weekend_pm=_int_or_none("predwkndPM"),
        dist_meters=_float_or_none("dist_meters"),
    )


def build_nearby_business(
    place: dict,
    category: str,
    survival_category: Optional[str],
) -> NearbyBusiness:
    """Convert a raw Google Places API dict into a NearbyBusiness dataclass."""
    address = place.get("formattedAddress")
    location = place.get("location", {})

    review_texts = [
        r.get("text", {}).get("text", "")
        for r in place.get("reviews", [])
        if r.get("text", {}).get("text")
    ]

    return NearbyBusiness(
        place_id=place.get("id", ""),
        name=place.get("displayName", {}).get("text", ""),
        category=category,
        survival_category=survival_category,
        address=address,
        zip_code=parse_zip_code(address) if address else None,
        rating=place.get("rating"),
        review_count=place.get("userRatingCount", 0),
        lat=location.get("latitude"),
        lng=location.get("longitude"),
        review_texts=review_texts,
    )


def build_neighborhood_scan(
    restaurant_data: dict,
    restaurant_yelp: list[dict],
    retail_data: dict,
) -> list[dict]:
    """
    Assemble a serializable list of CategoryScan dicts from raw scan data.

    Args:
        restaurant_data: results dict from scrape_area(), keyed by category.
            Each value has count, avg_rating, top_rating, top_review_count,
            and the new "places" list of raw Google Places objects.
        restaurant_yelp: output of enrich_and_rank(). List of dicts with
            "cat" (category name) and "y" (Yelp analysis dict or None).
        retail_data: raw market data from the retail scan loop, keyed by
            category → list of raw Google Places objects.

    Returns:
        JSON-serializable list of CategoryScan dicts for storage in
        properties.neighborhood_scan.
    """
    yelp_by_cat = {}
    for entry in restaurant_yelp:
        if entry.get("y"):
            yelp_by_cat[entry["cat"]] = entry["y"]

    scans: list[CategoryScan] = []

    # ── Restaurant categories ────────────────────────────────────────────
    for cat, d in restaurant_data.items():
        survival_cat = GPLACE_TO_SURVIVABILITY_CATEGORY.get(cat, "accommodation_and_food_services")
        places_raw = d.get("places", [])

        businesses = [
            build_nearby_business(p, cat, survival_cat)
            for p in places_raw
        ]

        # Per-business foot traffic lookups
        for biz in businesses:
            if biz.lat is not None and biz.lng is not None:
                biz.foot_traffic = build_foot_traffic(biz.lat, biz.lng)

        yelp = yelp_by_cat.get(cat)

        scans.append(CategoryScan(
            category=cat,
            survival_category=survival_cat,
            count=d.get("count", 0),
            avg_rating=d.get("avg_rating"),
            top_rating=d.get("top_rating"),
            top_review_count=d.get("top_review_count", 0),
            businesses=businesses,
            complaint_rate=yelp.get("complaint_rate") if yelp else None,
            wait_rate=yelp.get("wait_rate") if yelp else None,
        ))

    # ── Retail categories ────────────────────────────────────────────────
    for cat, places_raw in retail_data.items():
        survival_cat = GPLACE_TO_SURVIVABILITY_CATEGORY.get(cat, "retail_trade")

        businesses = [
            build_nearby_business(p, cat, survival_cat)
            for p in places_raw
        ]

        for biz in businesses:
            if biz.lat is not None and biz.lng is not None:
                biz.foot_traffic = build_foot_traffic(biz.lat, biz.lng)

        count = len(places_raw)
        rated = [p for p in places_raw if p.get("rating")]
        avg_rating = round(sum(p["rating"] for p in rated) / len(rated), 2) if rated else None
        top_place = max(rated, key=lambda p: p.get("rating", 0)) if rated else None
        top_rating = top_place.get("rating") if top_place else None
        top_review_count = max(
            (p.get("userRatingCount", 0) for p in places_raw), default=0
        )

        scans.append(CategoryScan(
            category=cat,
            survival_category=survival_cat,
            count=count,
            avg_rating=avg_rating,
            top_rating=top_rating,
            top_review_count=top_review_count,
            businesses=businesses,
        ))

    return [asdict(s) for s in scans]


# ── Rescore Reconstruction ───────────────────────────────────────────────────

# Partition by actual Google Places type, not survival_category.
# hotel/motel share survival_category with restaurants but are scanned as retail.
from RestaurantAnalysis.FullAPIPull import CATEGORIES as _RESTAURANT_CATEGORY_LIST

_RESTAURANT_GPLACE_TYPES = set(_RESTAURANT_CATEGORY_LIST)


def reconstruct_restaurant_inputs(
    scan: list[dict],
) -> tuple[dict, int, dict]:
    """
    Rebuild the inputs that calculate_hybrid_score() needs from stored JSONB.

    Returns:
        google_data: dict keyed by category with count, avg_rating, top_rating,
                     top_review_count, top_place, top_place_address, top_place_id
        total_found: total unique establishment count across all restaurant cats
        yelp_by_cat: dict keyed by category with complaint_rate, wait_rate
    """
    google_data: dict = {}
    yelp_by_cat: dict = {}
    all_place_ids: set = set()

    for cs in scan:
        if cs["category"] not in _RESTAURANT_GPLACE_TYPES:
            continue

        cat = cs["category"]
        businesses = cs.get("businesses", [])

        top_biz = max(businesses, key=lambda b: b.get("rating") or 0) if businesses else None

        google_data[cat] = {
            "count": cs.get("count", 0),
            "avg_rating": cs.get("avg_rating"),
            "top_rating": cs.get("top_rating"),
            "top_review_count": cs.get("top_review_count", 0),
            "top_place": top_biz["name"] if top_biz else "",
            "top_place_address": top_biz.get("address", "") if top_biz else "",
            "top_place_id": top_biz["place_id"] if top_biz else "",
        }

        for b in businesses:
            all_place_ids.add(b["place_id"])

        cr = cs.get("complaint_rate")
        wr = cs.get("wait_rate")
        if cr is not None or wr is not None:
            yelp_by_cat[cat] = {
                "complaint_rate": cr or 0,
                "wait_rate": wr or 0,
            }

    return google_data, len(all_place_ids), yelp_by_cat


def reconstruct_retail_inputs(scan: list[dict]) -> dict:
    """
    Rebuild the raw_market_data dict that calculate_hub_aware_opportunity() expects
    from stored JSONB, including review text for friction analysis.

    Returns:
        dict keyed by category -> list of place-like dicts with rating,
        userRatingCount, and reviews in the Google Places API shape.
    """
    raw_market_data: dict = {}

    for cs in scan:
        if cs["category"] in _RESTAURANT_GPLACE_TYPES:
            continue

        cat = cs["category"]
        places = []
        for biz in cs.get("businesses", []):
            place = {
                "id": biz["place_id"],
                "displayName": {"text": biz["name"]},
                "rating": biz.get("rating"),
                "userRatingCount": biz.get("review_count", 0),
                "reviews": [
                    {"text": {"text": t}} for t in biz.get("review_texts", [])
                ],
            }
            places.append(place)

        raw_market_data[cat] = places

    return raw_market_data
