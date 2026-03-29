"""
ml_interface.py
───────────────
Data contract between the neighborhood scan pipeline (Oliver)
and the ML survivability/revenue model (Ryan).

Oliver provides: get_ml_input(property_id) → PropertyMLInput
Ryan provides:   predict(PropertyMLInput) → PropertyMLOutput

Nothing here hits an API. Oliver's caching layer populates the DB;
this module reads from it and shapes the data.

Data sources:
  - Google Places API → category counts, ratings, reviews
  - SerpAPI/Yelp     → complaint_rate, wait_rate (restaurants only)
  - NYC Open Data    → business age (DOHMH inspections for restaurants,
                       DCWP licenses for retail). Free, no API key.
  - pckl.py          → foot traffic from NYC pedestrian network GeoJSON
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional
from ML_Algorithm import ProfitPrediction as pp
import requests
from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


# ── What Oliver gives the ML model ────────────────────────────────────────────


@dataclass
class FootTraffic:
    """Pedestrian counts at a single point (property or nearby business)."""
    weekday_am: Optional[int] = None   # 8-9 AM
    weekday_mid: Optional[int] = None  # 12:30-1:30 PM
    weekday_pm: Optional[int] = None   # 5-6 PM
    weekend_am: Optional[int] = None
    weekend_mid: Optional[int] = None
    weekend_pm: Optional[int] = None
    dist_meters: Optional[float] = None  # distance to nearest sidewalk segment


@dataclass
class NearbyBusiness:
    """A single existing business found near the property."""
    place_id: str
    name: str
    category: str                                   # Google Places type
    survival_category: Optional[str] = None         # mapped historical bucket
    address: Optional[str] = None                   # from Google Places formattedAddress
    zip_code: Optional[str] = None                  # parsed from address
    rating: Optional[float] = None
    review_count: int = 0
    lat: Optional[float] = None
    lng: Optional[float] = None
    business_age_years: Optional[float] = None      # from NYC Open Data (Phase 2)
    foot_traffic: Optional[FootTraffic] = None      # per-business traffic from pckl.py
    review_texts: list[str] = field(default_factory=list)  # Google review text for sentiment/friction rescore


@dataclass
class CategoryScan:
    """
    Everything we know about ONE Google Places category in the property's radius.
    count == 0 means this category has no nearby competitors.
    """
    category: str                        # Google Places type, e.g. "italian_restaurant"
    survival_category: str               # mapped historical bucket, e.g. "full_service_restaurant"
    count: int = 0                       # how many exist nearby
    avg_rating: Optional[float] = None
    top_rating: Optional[float] = None
    top_review_count: int = 0
    businesses: list[NearbyBusiness] = field(default_factory=list)

    # Yelp enrichment (restaurants only, None for retail)
    complaint_rate: Optional[float] = None
    wait_rate: Optional[float] = None

    # Business age (from NYC Open Data, None for zero-count categories)
    avg_business_age_years: Optional[float] = None


@dataclass
class PropertyMLInput:
    """
    Complete input package for the ML model for ONE property.
    Contains the property's foot traffic + every category scan.
    """
    property_id: str
    lat: float
    lng: float
    address: str

    # foot traffic at the property itself
    property_foot_traffic: FootTraffic

    # one entry per category (including zeros)
    categories: list[CategoryScan]


# ── What the ML model returns ─────────────────────────────────────────────────


@dataclass
class CategoryPrediction:
    """ML output for a single business category at this property."""
    category: str                         # Google Places type
    survival_probability: float           # 0-1
    estimated_capture_rate: float         # fraction of foot traffic that converts
    estimated_annual_revenue: float       # dollars


@dataclass
class PropertyMLOutput:
    """Full ML output for one property."""
    property_id: str
    predictions: list[CategoryPrediction]


# ── Stub loader (Oliver replaces internals, signature stays fixed) ────────────


def _deserialize_foot_traffic(d: dict | None) -> FootTraffic | None:
    if d is None:
        return None
    return FootTraffic(**{k: d.get(k) for k in FootTraffic.__dataclass_fields__})


def _deserialize_business(d: dict) -> NearbyBusiness:
    ft = _deserialize_foot_traffic(d.get("foot_traffic"))
    return NearbyBusiness(
        place_id=d["place_id"],
        name=d["name"],
        category=d["category"],
        survival_category=d.get("survival_category"),
        address=d.get("address"),
        zip_code=d.get("zip_code"),
        rating=d.get("rating"),
        review_count=d.get("review_count", 0),
        lat=d.get("lat"),
        lng=d.get("lng"),
        business_age_years=d.get("business_age_years"),
        foot_traffic=ft,
        review_texts=d.get("review_texts", []),
    )


def _deserialize_category_scan(d: dict) -> CategoryScan:
    businesses = [_deserialize_business(b) for b in d.get("businesses", [])]
    return CategoryScan(
        category=d["category"],
        survival_category=d["survival_category"],
        count=d.get("count", 0),
        avg_rating=d.get("avg_rating"),
        top_rating=d.get("top_rating"),
        top_review_count=d.get("top_review_count", 0),
        businesses=businesses,
        complaint_rate=d.get("complaint_rate"),
        wait_rate=d.get("wait_rate"),
        avg_business_age_years=d.get("avg_business_age_years"),
    )


def get_ml_input(property_id: str) -> PropertyMLInput:
    """
    Reads from neighborhood_scan JSONB in Supabase and deserializes into
    PropertyMLInput. Falls back to mock_ml_input() when env vars are missing
    (e.g. during Ryan's local development).
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        return mock_ml_input()

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }
    params = {
        "select": "id,address,latitude,longitude,neighborhood_scan",
        "id": f"eq.{property_id}",
    }
    resp = requests.get(
        f"{supabase_url}/rest/v1/properties",
        headers=headers,
        params=params,
    )
    resp.raise_for_status()

    rows = resp.json()
    if not rows:
        raise ValueError(f"Property {property_id} not found")

    row = rows[0]
    scan_data = row.get("neighborhood_scan")
    if scan_data is None:
        raise ValueError(
            f"Property {property_id} has no neighborhood_scan data. "
            "Run backfill-analysis.py --full-scan first."
        )

    if isinstance(scan_data, str):
        scan_data = json.loads(scan_data)

    categories = [_deserialize_category_scan(d) for d in scan_data]

    from neighborhood_scan import build_foot_traffic  # avoid circular import at module level
    property_ft = build_foot_traffic(row["latitude"], row["longitude"])

    return PropertyMLInput(
        property_id=property_id,
        lat=row["latitude"],
        lng=row["longitude"],
        address=row["address"],
        property_foot_traffic=property_ft,
        categories=categories,
    )


def mock_ml_input() -> PropertyMLInput:
    """
    Hardcoded example so Ryan can develop against real-shaped data.
    Represents a property near Chinatown/NoLiTa.
    """
    return PropertyMLInput(
        property_id="test-property-001",
        lat=40.7258,
        lng=-73.9932,
        address="123 Mott St, New York, NY 10013",
        property_foot_traffic=FootTraffic(
            weekday_am=1200,
            weekday_mid=3400,
            weekday_pm=2800,
            weekend_am=900,
            weekend_mid=4100,
            weekend_pm=3500,
            dist_meters=4.2,
        ),
        categories=[
            # ── Restaurant with competitors + Yelp enrichment ─────────
            CategoryScan(
                category="italian_restaurant",
                survival_category="accommodation_and_food_services",
                count=5,
                avg_rating=3.9,
                top_rating=4.3,
                top_review_count=230,
                complaint_rate=0.12,
                wait_rate=0.08,
                avg_business_age_years=8.3,
                businesses=[
                    NearbyBusiness(
                        place_id="ChIJ_example1",
                        name="Lombardi's Pizza",
                        category="italian_restaurant",
                        survival_category="accommodation_and_food_services",
                        address="32 Spring St, New York, NY 10012",
                        zip_code="10012",
                        rating=4.3,
                        review_count=230,
                        lat=40.7256,
                        lng=-73.9955,
                        business_age_years=12.5,
                        foot_traffic=FootTraffic(
                            weekday_am=950,
                            weekday_mid=2800,
                            weekday_pm=2200,
                            weekend_am=700,
                            weekend_mid=3400,
                            weekend_pm=2900,
                            dist_meters=8.1,
                        ),
                    ),
                ],
            ),
            # ── Dense restaurant category ─────────────────────────────
            CategoryScan(
                category="chinese_restaurant",
                survival_category="accommodation_and_food_services",
                count=18,
                avg_rating=3.7,
                top_rating=4.5,
                top_review_count=890,
                complaint_rate=0.22,
                wait_rate=0.15,
                avg_business_age_years=11.2,
                businesses=[],
            ),
            # ── Gap category (zero nearby) ────────────────────────────
            CategoryScan(
                category="acai_shop",
                survival_category="accommodation_and_food_services",
                count=0,
                businesses=[],
            ),
            # ── Retail category (no Yelp data) ────────────────────────
            CategoryScan(
                category="grocery_store",
                survival_category="retail_trade",
                count=3,
                avg_rating=4.1,
                top_rating=4.4,
                top_review_count=540,
                avg_business_age_years=6.7,
                businesses=[],
            ),
        ],
    )


# ── Ryan's entry point (he implements this) ───────────────────────────────────


def predict(ml_input: PropertyMLInput) -> PropertyMLOutput:
    """
    Ryan implements this. Takes the full property context,
    returns survivability + revenue predictions per category.
    """
    zip = None
    traffic_data =None
    nearby_competitors = None
    survival_cat = None
    avg_traffic = pp.calculate_average_traffic(traffic_data)
    capture_rate = pp.get_advanced_features(zip, avg_traffic, survival_cat)['traffic_efficiency']
    base_survival_rate_5 = pp.INDUSTRY_PROFILES[survival_cat]['rate'][4]
    score = pp.predict_lot_success_ml(zip, avg_traffic, survival_cat, 0, nearby_competitors)
    raise NotImplementedError("Ryan is building this")
