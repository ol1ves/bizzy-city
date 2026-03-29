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
import math
import os
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import requests
from dotenv import load_dotenv

try:
    from ML_Algorithm import ProfitPrediction as pp
except Exception:
    pp = None

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
    zip_code: Optional[str] = None

    # foot traffic at the property itself
    property_foot_traffic: FootTraffic = field(default_factory=FootTraffic)

    # one entry per category (including zeros)
    categories: list[CategoryScan] = field(default_factory=list)


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
        "select": "id,address,latitude,longitude,zip_code,neighborhood_scan",
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
        zip_code=row.get("zip_code"),
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
        zip_code="10013",
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


# ── Fallback constants (mirrors ProfitPrediction.py for when .pkl is absent) ──

_INDUSTRY_PROFILES = {
    'accommodation_and_food_services': {
        'rate': [0.829, 0.724, 0.648, 0.587, 0.536, 0.377], 'friction': 1.1,
    },
    'health_care_and_social_assistance': {
        'rate': [0.827, 0.732, 0.661, 0.603, 0.555, 0.395], 'friction': 0.7,
    },
    'retail_trade': {
        'rate': [0.846, 0.746, 0.670, 0.610, 0.558, 0.391], 'friction': 1.3,
    },
    'arts_entertainment_and_recreation': {
        'rate': [0.813, 0.706, 0.624, 0.559, 0.505, 0.327], 'friction': 1.2,
    },
    'real_estate_and_rental_and_leasing': {
        'rate': [0.832, 0.733, 0.658, 0.596, 0.547, 0.370], 'friction': 2.0,
    },
    'other_services': {
        'rate': [0.827, 0.731, 0.657, 0.596, 0.546, 0.376], 'friction': 1.0,
    },
}

_NYC_INCOMES = {
    '10032': 27257, '10033': 27257, '10040': 27257, '10034': 27257, '10463': 27257,
    '10031': 26694, '10027': 26694,
    '10030': 34463, '10037': 34463, '10039': 34463,
    '10029': 22975, '10035': 22975,
    '10023': 85724, '10024': 85724, '10025': 85724, '10069': 85724,
    '10021': 87724, '10028': 87724, '10044': 87724, '10065': 87724,
    '10075': 87724, '10128': 87724,
    '10001': 77071, '10011': 77071, '10018': 77071, '10019': 77071,
    '10020': 77071, '10036': 77071,
    '10010': 83546, '10016': 83546, '10017': 83546, '10022': 83546,
    '10004': 93990, '10005': 93990, '10006': 93990, '10007': 93990,
    '10012': 93990, '10013': 93990, '10014': 93990, '10280': 93990,
    '10002': 23393, '10003': 23393, '10009': 23393,
}


def _get_profiles() -> dict:
    return pp.INDUSTRY_PROFILES if pp else _INDUSTRY_PROFILES


def _foot_traffic_to_dict(ft: FootTraffic) -> dict:
    return {
        'weekday_am': ft.weekday_am or 0,
        'weekday_mid': ft.weekday_mid or 0,
        'weekday_pm': ft.weekday_pm or 0,
        'weekend_am': ft.weekend_am or 0,
        'weekend_mid': ft.weekend_mid or 0,
        'weekend_pm': ft.weekend_pm or 0,
    }


def _calc_avg_traffic(traffic_dict: dict) -> float:
    if pp:
        return pp.calculate_average_traffic(traffic_dict)
    weekday = traffic_dict['weekday_am'] + traffic_dict['weekday_mid'] + traffic_dict['weekday_pm']
    weekend = traffic_dict['weekend_am'] + traffic_dict['weekend_mid'] + traffic_dict['weekend_pm']
    return round(((weekday * 5) + (weekend * 2)) / 7, 2)


def _get_advanced_feats(zip_code: str | None, foot_traffic: float, industry_label: str) -> dict:
    if pp:
        return pp.get_advanced_features(zip_code, foot_traffic, industry_label)
    profiles = _INDUSTRY_PROFILES
    base_income = _NYC_INCOMES.get(str(zip_code), 35000) if zip_code else 35000
    friction = profiles[industry_label].get('friction', 1.0)
    if base_income > 85000:
        tier = 3
    elif base_income > 70000:
        tier = 2
    elif base_income > 30000:
        tier = 1
    else:
        tier = 0
    return {
        'income_proxy': base_income,
        'traffic_volume': foot_traffic,
        'neighborhood_tier': tier,
        'spend_capacity': foot_traffic * (base_income / 100_000),
        'traffic_efficiency': math.log1p(foot_traffic) / friction,
        'industry_friction': friction,
    }


def _build_competitors(cat_scan: CategoryScan, avg_property_traffic: float) -> list[dict]:
    """Map NearbyBusiness list to the dict format ProfitPrediction expects."""
    comps = []
    for biz in cat_scan.businesses:
        biz_traffic = avg_property_traffic
        if biz.foot_traffic:
            biz_traffic = _calc_avg_traffic(_foot_traffic_to_dict(biz.foot_traffic))
        comps.append({
            'years_open': biz.business_age_years or 0,
            'foot_traffic': biz_traffic,
        })
    return comps


def _formula_score(survival_cat: str, feats: dict, competitors: list[dict]) -> float:
    """Heuristic score (0-100) when the trained .pkl model is unavailable."""
    profiles = _INDUSTRY_PROFILES
    base_rate = profiles[survival_cat]['rate'][4]
    tier_bonus = feats['neighborhood_tier'] * 5
    comp_count = len(competitors)
    competition_penalty = min(comp_count * 2, 30)
    score = base_rate * 100 + tier_bonus - competition_penalty
    return max(0.0, min(score, 100.0))


# ── Prediction entry point ───────────────────────────────────────────────────


def predict(ml_input: PropertyMLInput) -> PropertyMLOutput:
    """
    Run the ML survivability/revenue model for every category in the input.
    Uses ProfitPrediction.pkl when available, falls back to formula-based
    scoring otherwise.
    """
    zip_code = ml_input.zip_code
    traffic_dict = _foot_traffic_to_dict(ml_input.property_foot_traffic)
    avg_traffic = _calc_avg_traffic(traffic_dict)
    profiles = _get_profiles()
    INDUSTRY_DIVISORS = {
        'accommodation_and_food_services': 2000,
        'retail_trade': 1500,
        'real_estate_and_rental_and_leasing': 500,
        'other_services': 3000,
        'health_care_and_social_assistance': 1000,  # High per-visit insurance cost
        'arts_entertainment_and_recreation': 2200  # Ticket-based pricing
    }

    predictions: list[CategoryPrediction] = []
    for cat_scan in ml_input.categories:
        survival_cat = cat_scan.survival_category
        if survival_cat not in profiles:
            continue

        competitors = _build_competitors(cat_scan, avg_traffic)
        feats = _get_advanced_feats(zip_code, avg_traffic, survival_cat)

        if pp:
            score = float(pp.predict_lot_success_ml(
                zip_code, avg_traffic, survival_cat, 0, competitors,
            ))
        else:
            score = _formula_score(survival_cat, feats, competitors)

            # 2. Survival probability (linked to ML score)
            base_rate_5yr = profiles[survival_cat]['rate'][4]
            survival_prob = min(base_rate_5yr * (score / 50.0), 1.0)

            # 3. Capture Rate Logic (Standardizing the 9.0 efficiency into ~2-5%)
            friction = feats['industry_friction']
            capture_rate = (np.log1p(avg_traffic) * 0.012) / (friction ** 1.5)
            capture_rate = min(max(capture_rate, 0.005), 0.12)

            # 4. Headcount: Who actually walks in?
            captured_daily_traffic = avg_traffic * capture_rate

            # 5. Dynamic Average Transaction Value (ATV)
            # Get the divisor for this specific category, defaulting to 2500 if not found
            divisor = INDUSTRY_DIVISORS.get(survival_cat, 2500)
            avg_transaction_value = feats['income_proxy'] / divisor

            # 6. Annual Revenue Calculation
            # (Captured Daily Traffic) * (Spend per Visit) * (365 Days) * (Success Modifier)
            annual_revenue = captured_daily_traffic * avg_transaction_value * 365 * (score / 100.0)

            predictions.append(CategoryPrediction(
                category=cat_scan.category,
                survival_probability=round(survival_prob, 4),
                estimated_capture_rate=round(capture_rate, 4),
                estimated_annual_revenue=round(annual_revenue, 2),
            ))

    predictions.sort(key=lambda p: p.survival_probability, reverse=True)
    return PropertyMLOutput(property_id=ml_input.property_id, predictions=predictions)
