"""
backfill-analysis.py
────────────────────
Back-populate analysis columns for properties in Supabase.

Supports four analysis types: restaurant, retail, foot_traffic, ml.
Only processes properties where the relevant column is NULL or empty,
unless --force is passed.

--full-scan runs all three analyses PLUS builds the neighborhood_scan JSONB
for the ML pipeline, writing all four columns in a single PATCH per property.

--predict runs the ML survivability/revenue model from cached JSONB (no API
calls). Results are stored in properties.ml_predictions.

Usage:
    python backfill-analysis.py                            # run all four (1 property, confirmation prompt)
    python backfill-analysis.py --property-id <uuid>      # target one specific property
    python backfill-analysis.py --types restaurant         # restaurant only
    python backfill-analysis.py --types retail foot_traffic ml
    python backfill-analysis.py --force                    # re-analyze everything
    python backfill-analysis.py --dry-run                  # simulate with stub data, no APIs called
    python backfill-analysis.py --full-scan                # all analyses + JSONB + ML predictions
    python backfill-analysis.py --full-scan --limit 5 -y   # process 5 properties, skip confirmation
    python backfill-analysis.py --rescore                  # re-run formulas from cached JSONB (no API calls)
    python backfill-analysis.py --predict                  # run ML model from cached JSONB (no API calls)
    python backfill-analysis.py --limit 0                  # process ALL properties (0 = no limit)

Env vars (loaded from ../.env):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
    GOOGLE_API_KEY
    SERPAPI_KEY
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from RestaurantAnalysis import get_restaurant_analysis
from RestaurantAnalysis.FullAPIPull import scrape_area, opportunity_score, enrich_and_rank, calculate_hybrid_score, CATEGORIES as RESTAURANT_CATEGORIES
from RetailAnalysis import get_retail_analysis
from RetailAnalysis.RetailAPIPull import CATEGORIES as RETAIL_CATEGORIES, search_nearby_retail, calculate_hub_aware_opportunity
from FootTraffic import get_foot_traffic_analysis
from dataclasses import asdict
from neighborhood_scan import (
    build_neighborhood_scan,
    build_foot_traffic,
    reconstruct_restaurant_inputs,
    reconstruct_retail_inputs,
)
from ml_interface import (
    PropertyMLInput,
    predict,
    _deserialize_category_scan,
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

ALL_TYPES = ["restaurant", "retail", "foot_traffic", "ml"]

ANALYSIS_MAP = {
    "restaurant": {
        "column": "restaurant_analysis",
        "fn": get_restaurant_analysis,
    },
    "retail": {
        "column": "retail_analysis",
        "fn": get_retail_analysis,
    },
    "foot_traffic": {
        "column": "foot_traffic_analysis",
        "fn": get_foot_traffic_analysis,
    },
}

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

REQUIRED_COLUMNS = [
    "neighborhood_scan",
    "restaurant_analysis",
    "retail_analysis",
    "foot_traffic_analysis",
    "ml_predictions",
]


def _check_db_connection() -> None:
    """
    Pre-flight: verify Supabase is reachable, credentials are valid,
    and all required columns exist on the properties table.
    Exits on failure so we never start expensive API calls only to
    fail at write time.
    """
    print("Pre-flight DB check...")

    # 1. Read check
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/properties",
            headers=HEADERS,
            params={"select": "id", "limit": "1"},
        )
    except requests.ConnectionError as e:
        sys.exit(f"  FAIL: cannot reach Supabase at {SUPABASE_URL}\n  {e}")

    if resp.status_code == 401:
        sys.exit("  FAIL: SUPABASE_SERVICE_KEY is invalid (401 Unauthorized)")
    if not resp.ok:
        sys.exit(f"  FAIL: Supabase returned {resp.status_code}: {resp.text}")

    print("  OK   read access")

    # 2. Column existence check (attempt selecting every required column)
    col_select = ",".join(REQUIRED_COLUMNS)
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/properties",
        headers=HEADERS,
        params={"select": f"id,{col_select}", "limit": "1"},
    )
    if resp.status_code == 400:
        sys.exit(
            f"  FAIL: one or more required columns missing from properties table.\n"
            f"  Required: {REQUIRED_COLUMNS}\n"
            f"  Run the pending Supabase migration first.\n"
            f"  Supabase response: {resp.text}"
        )
    if not resp.ok:
        sys.exit(f"  FAIL: column check returned {resp.status_code}: {resp.text}")

    print("  OK   required columns exist")

    # 3. Write check — PATCH a non-existent ID so nothing actually changes
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/properties?id=eq.00000000-0000-0000-0000-000000000000",
        headers=HEADERS,
        json={"address": "__write_check__"},
    )
    if resp.status_code in (401, 403):
        sys.exit(f"  FAIL: write permission denied ({resp.status_code})")

    print("  OK   write access")
    print()

_DRY_RUN_PROPERTIES = [
    {"id": "dry-1", "address": "123 Broadway, New York, NY",    "latitude": 40.7258, "longitude": -73.9932},
    {"id": "dry-2", "address": "456 5th Ave, New York, NY",     "latitude": 40.7527, "longitude": -73.9772},
    {"id": "dry-3", "address": "789 Atlantic Ave, Brooklyn, NY","latitude": 40.6839, "longitude": -73.9754},
]

_DRY_RUN_STUBS = {
    "restaurant": (
        "1. pizza_restaurant | Score: 1234.5 | Share: 12.3% | Pain: LOW\n"
        "2. coffee_shop      | Score:  876.2 | Share:  8.7% | Pain: MED\n"
        "[dry-run stub]"
    ),
    "retail": (
        "1. grocery_store | Score: 567.8 | Share: 8.5% | Pain: MED\n"
        "2. beauty_salon  | Score: 312.4 | Share: 5.1% | Pain: LOW\n"
        "[dry-run stub]"
    ),
    "foot_traffic": (
        "Weekday AM (8-9): 1,234\n"
        "Weekday Midday (12:30-1:30): 2,345\n"
        "Weekday PM (5-6): 3,102\n"
        "Weekend AM (8-9): 891\n"
        "Weekend Midday (12:30-1:30): 1,678\n"
        "Weekend PM (5-6): 2,210\n"
        "Nearest sidewalk segment: 4.2m away\n"
        "[dry-run stub]"
    ),
}


# ── Pre-flight & Approval ────────────────────────────────────────────────────

_API_COSTS = {
    "restaurant": {
        "Google Places": f"{len(RESTAURANT_CATEGORIES)} searchNearby",
        "SerpAPI (Yelp)": "15-30 (place + reviews)",
        "google_per_prop": len(RESTAURANT_CATEGORIES),
        "serp_min": 15,
        "serp_max": 30,
    },
    "retail": {
        "Google Places": f"{len(RETAIL_CATEGORIES)} searchNearby",
        "google_per_prop": len(RETAIL_CATEGORIES),
        "serp_min": 0,
        "serp_max": 0,
    },
    "foot_traffic": {
        "google_per_prop": 0,
        "serp_min": 0,
        "serp_max": 0,
    },
    "ml": {
        "google_per_prop": 0,
        "serp_min": 0,
        "serp_max": 0,
    },
    "full_scan": {
        "Google Places (restaurant)": f"{len(RESTAURANT_CATEGORIES)} searchNearby",
        "Google Places (retail)": f"{len(RETAIL_CATEGORIES)} searchNearby",
        "SerpAPI (Yelp)": "15-30 (place + reviews)",
        "google_per_prop": len(RESTAURANT_CATEGORIES) + len(RETAIL_CATEGORIES),
        "serp_min": 15,
        "serp_max": 30,
    },
}


def _preflight_summary(mode: str, properties: list[dict], types: list[str] | None = None) -> bool:
    """
    Print API cost summary. Returns True if external API calls will be made.
    """
    n = len(properties)

    if mode in ("rescore", "predict"):
        print(f"\n  Mode:       --{mode}")
        print(f"  Properties: {n}")
        print(f"  External API calls: 0 (runs from cached data)")
        return False

    if mode == "full_scan":
        cost = _API_COSTS["full_scan"]
        google_total = n * cost["google_per_prop"]
        serp_min = n * cost["serp_min"]
        serp_max = n * cost["serp_max"]

        print()
        print("=" * 55)
        print("  Backfill Pre-flight Summary")
        print("=" * 55)
        print(f"  Mode:       --full-scan")
        print(f"  Properties: {n}")
        print("-" * 55)
        print("  API calls per property:")
        for label, desc in cost.items():
            if label.startswith(("google_", "serp_")):
                continue
            print(f"    {label}: {desc}")
        print("-" * 55)
        print(f"  Estimated totals:")
        print(f"    Google Places:  {google_total} calls  ({n} x {cost['google_per_prop']})")
        print(f"    SerpAPI:        {serp_min}-{serp_max} calls  ({n} x {cost['serp_min']}-{cost['serp_max']})")
        print("-" * 55)
        print("  Properties:")
        for i, p in enumerate(properties, 1):
            print(f"    {i}. {p.get('address') or p['id']}")
        print("=" * 55)

        return google_total > 0 or serp_max > 0

    # --types mode: summarize each requested type
    active_types = types or ALL_TYPES
    total_google = 0
    total_serp_min = 0
    total_serp_max = 0

    api_lines = []
    for t in active_types:
        cost = _API_COSTS.get(t, {})
        g = cost.get("google_per_prop", 0)
        s_min = cost.get("serp_min", 0)
        s_max = cost.get("serp_max", 0)
        total_google += n * g
        total_serp_min += n * s_min
        total_serp_max += n * s_max
        for label, desc in cost.items():
            if label.startswith(("google_", "serp_")):
                continue
            api_lines.append(f"    {label} ({t}): {desc}")

    has_external = total_google > 0 or total_serp_max > 0
    if not has_external:
        print(f"\n  Mode:       --types {' '.join(active_types)}")
        print(f"  Properties: {n}")
        print(f"  External API calls: 0 (runs from cached/local data)")
        return False

    print()
    print("=" * 55)
    print("  Backfill Pre-flight Summary")
    print("=" * 55)
    print(f"  Mode:       --types {' '.join(active_types)}")
    print(f"  Properties: {n}")
    print("-" * 55)
    print("  API calls per property:")
    for line in api_lines:
        print(line)
    print("-" * 55)
    print(f"  Estimated totals:")
    if total_google > 0:
        print(f"    Google Places:  {total_google} calls")
    if total_serp_max > 0:
        print(f"    SerpAPI:        {total_serp_min}-{total_serp_max} calls")
    print("-" * 55)
    print("  Properties:")
    for i, p in enumerate(properties, 1):
        print(f"    {i}. {p.get('address') or p['id']}")
    print("=" * 55)

    return True


def _confirm_proceed(auto_approve: bool) -> bool:
    if auto_approve:
        print("  --yes flag: auto-approved.")
        return True
    try:
        answer = input("\nProceed? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer in ("y", "yes"):
        return True
    print("Aborted.")
    return False


def _apply_limit(properties: list, limit: int) -> list:
    if limit > 0:
        return properties[:limit]
    return properties


def fetch_properties(column: str, force: bool, property_id: str | None = None) -> list:
    params = {"select": f"id,address,latitude,longitude,{column}"}
    if not force:
        params["or"] = f"({column}.is.null,{column}.eq.)"
    if property_id:
        params["id"] = f"eq.{property_id}"

    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/properties", headers=HEADERS, params=params
    )
    if not resp.ok:
        sys.exit(f"Supabase error {resp.status_code}: {resp.text}")

    data = resp.json()
    if not isinstance(data, list):
        sys.exit(f"Unexpected response (expected list): {data}")
    return data


def run_analysis(analysis_type: str, force: bool, dry_run: bool = False,
                  limit: int = 1, auto_approve: bool = False,
                  property_id: str | None = None):
    cfg = ANALYSIS_MAP[analysis_type]
    column = cfg["column"]
    analyze = cfg["fn"]

    if dry_run:
        properties = _apply_limit(_DRY_RUN_PROPERTIES, limit)
        stub = _DRY_RUN_STUBS[analysis_type]
        print(f"\n[{analysis_type}] [DRY-RUN] {len(properties)} sample properties")
        for p in properties:
            label = p.get("address") or p["id"]
            lat, lng = p.get("latitude"), p.get("longitude")
            if not lat or not lng:
                print(f"  SKIP {label} -- missing lat/lng")
                continue
            preview = stub.replace("\n", " | ")[:80]
            print(f"  [DRY-RUN] WOULD PATCH {label}")
            print(f"            → {preview}")
        print(f"[{analysis_type}] [DRY-RUN] Done: {len(properties)}/{len(properties)} (simulated)")
        return

    properties = fetch_properties(column, force, property_id=property_id)
    properties = _apply_limit(properties, limit)

    needs_api = _preflight_summary("types", properties, types=[analysis_type])
    if needs_api and not _confirm_proceed(auto_approve):
        return

    print(f"\n[{analysis_type}] {len(properties)} properties to process")

    success = 0
    for p in properties:
        label = p.get("address") or p["id"]
        lat, lng = p.get("latitude"), p.get("longitude")

        if not lat or not lng:
            print(f"  SKIP {label} -- missing lat/lng")
            continue

        if not force and p.get(column) and str(p[column]).strip():
            print(f"  SKIP {label} -- already has {column}, skipping")
            continue

        try:
            result = analyze(lat, lng)
            if not result or not result.strip():
                print(f"  SKIP {label} -- analysis returned empty")
                continue

            resp = requests.patch(
                f"{SUPABASE_URL}/rest/v1/properties?id=eq.{p['id']}",
                headers=HEADERS,
                json={column: result},
            )
            resp.raise_for_status()
            success += 1
            print(f"  OK   {label}")
        except Exception as e:
            print(f"  FAIL {label} -- {e}")

    print(f"[{analysis_type}] Done: {success}/{len(properties)} succeeded")


def fetch_properties_for_scan(force: bool, property_id: str | None = None) -> list:
    """
    Fetch properties for full scan. When not --force, returns ALL properties
    so we can check each column individually for lazy updates.
    """
    params = {
        "select": "id,address,latitude,longitude,zip_code,"
                  "neighborhood_scan,restaurant_analysis,retail_analysis,"
                  "foot_traffic_analysis,ml_predictions",
    }
    if property_id:
        params["id"] = f"eq.{property_id}"

    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/properties", headers=HEADERS, params=params
    )
    if not resp.ok:
        sys.exit(f"Supabase error {resp.status_code}: {resp.text}")

    data = resp.json()
    if not isinstance(data, list):
        sys.exit(f"Unexpected response (expected list): {data}")
    return data


def _format_restaurant_text(final_ranked: list[dict]) -> str:
    """Reproduce the same text output as get_restaurant_analysis()."""
    lines = []
    for i, res in enumerate(final_ranked, 1):
        pain = "LOW"
        if res['y']:
            if res['y'].get('complaint_rate', 0) > 0.18:
                pain = "HIGH"
            elif res['y'].get('wait_rate', 0) > 0.12:
                pain = "MED"
        lines.append(
            f"{i}. {res['cat']} | Score: {res['score']} "
            f"| Share: {res['share']:.1%} "
            f"| Pain: {pain}"
        )
    return "\n".join(lines)


def _format_retail_text(rankings: list[dict]) -> str:
    """Reproduce the same text output as get_retail_analysis()."""
    if not rankings:
        return ""
    lines = []
    for i, res in enumerate(rankings[:25], 1):
        pain = "HIGH" if res['friction'] > 0.2 else "MED" if res['friction'] > 0.05 else "LOW"
        lines.append(
            f"{i}. {res['category']} | Score: {res['score']:.1f} "
            f"| Share: {res['share']:.1%} | Pain: {pain}"
        )
    return "\n".join(lines)


def _run_ml_predict(property_row: dict, scan_json: list[dict]) -> list[dict] | None:
    """
    Build PropertyMLInput from already-fetched data and run predict().
    Returns serialized predictions list, or None on failure.
    """
    try:
        categories = [_deserialize_category_scan(d) for d in scan_json]
        ft = build_foot_traffic(property_row["latitude"], property_row["longitude"])

        ml_input = PropertyMLInput(
            property_id=property_row["id"],
            lat=property_row["latitude"],
            lng=property_row["longitude"],
            address=property_row.get("address", ""),
            zip_code=property_row.get("zip_code"),
            property_foot_traffic=ft,
            categories=categories,
        )
        output = predict(ml_input)
        return [asdict(p) for p in output.predictions]
    except Exception as e:
        print(f"  ML predict failed: {e}")
        return None


def run_predict(force: bool, dry_run: bool = False,
                limit: int = 1, auto_approve: bool = False,
                property_id: str | None = None):
    """
    Run ML predictions from cached neighborhood_scan JSONB. Zero API calls.
    Writes results to properties.ml_predictions.
    """
    if dry_run:
        properties = _apply_limit(_DRY_RUN_PROPERTIES, limit)
        print(f"\n[predict] [DRY-RUN] {len(properties)} sample properties")
        for p in properties:
            label = p.get("address") or p["id"]
            print(f"  [DRY-RUN] WOULD run ML predict for {label}")
        print(f"[predict] [DRY-RUN] Done: {len(properties)}/{len(properties)} (simulated)")
        return

    params = {"select": "id,address,latitude,longitude,zip_code,neighborhood_scan,ml_predictions"}
    if not force:
        params["neighborhood_scan"] = "not.is.null"
    if property_id:
        params["id"] = f"eq.{property_id}"

    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/properties", headers=HEADERS, params=params
    )
    if not resp.ok:
        sys.exit(f"Supabase error {resp.status_code}: {resp.text}")

    properties = resp.json()
    if not isinstance(properties, list):
        sys.exit(f"Unexpected response (expected list): {properties}")

    properties = _apply_limit(properties, limit)
    _preflight_summary("predict", properties)

    print(f"\n[predict] {len(properties)} properties to process")

    success = 0
    for p in properties:
        label = p.get("address") or p["id"]
        scan_data = p.get("neighborhood_scan")
        if not scan_data:
            print(f"  SKIP {label} -- no neighborhood_scan data")
            continue

        if not force and p.get("ml_predictions"):
            print(f"  SKIP {label} -- already has ml_predictions")
            continue

        if isinstance(scan_data, str):
            scan_data = json.loads(scan_data)

        predictions = _run_ml_predict(p, scan_data)
        if predictions is None:
            print(f"  FAIL {label} -- prediction returned None")
            continue

        try:
            resp = requests.patch(
                f"{SUPABASE_URL}/rest/v1/properties?id=eq.{p['id']}",
                headers=HEADERS,
                json={"ml_predictions": predictions},
            )
            resp.raise_for_status()
            success += 1
            print(f"  OK   {label} ({len(predictions)} categories predicted)")
        except Exception as e:
            print(f"  FAIL {label} -- {e}")

    print(f"[predict] Done: {success}/{len(properties)} succeeded")


def _needs_work(p: dict, force: bool) -> dict:
    """
    Inspect a property row and return which pieces still need work.
    Returns a dict of booleans: {scan, restaurant, retail, foot_traffic, ml}.
    """
    if force:
        return {"scan": True, "restaurant": True, "retail": True, "foot_traffic": True, "ml": True}

    has_scan = bool(p.get("neighborhood_scan"))
    return {
        "scan": not has_scan,
        "restaurant": not bool(p.get("restaurant_analysis")),
        "retail": not bool(p.get("retail_analysis")),
        "foot_traffic": not bool(p.get("foot_traffic_analysis")),
        "ml": not bool(p.get("ml_predictions")),
    }


def run_full_scan(force: bool, dry_run: bool = False,
                  limit: int = 1, auto_approve: bool = False,
                  property_id: str | None = None):
    """Run all three analyses + JSONB assembly + ML predictions per property."""
    if dry_run:
        properties = _apply_limit(_DRY_RUN_PROPERTIES, limit)
        print(f"\n[full-scan] [DRY-RUN] {len(properties)} sample properties")
        for p in properties:
            label = p.get("address") or p["id"]
            print(f"  [DRY-RUN] WOULD run restaurant + retail + foot_traffic + JSONB for {label}")
        print(f"[full-scan] [DRY-RUN] Done: {len(properties)}/{len(properties)} (simulated)")
        return

    all_properties = fetch_properties_for_scan(force, property_id=property_id)
    all_properties = _apply_limit(all_properties, limit)

    # Filter to properties that actually need at least one update
    properties = []
    for p in all_properties:
        work = _needs_work(p, force)
        if any(work.values()):
            properties.append(p)

    if not properties:
        print("\n[full-scan] All properties are already up to date. Nothing to do.")
        return

    # Only count API calls for properties that need the scan (API-heavy part)
    need_api_count = sum(1 for p in properties if _needs_work(p, force)["scan"])
    if need_api_count < len(properties):
        print(f"\n  {len(all_properties)} total properties, "
              f"{len(properties)} need updates, "
              f"{need_api_count} need new API scans")

    needs_api = need_api_count > 0
    if needs_api:
        _preflight_summary("full_scan", properties[:need_api_count] if not force else properties)
    else:
        print(f"\n  Mode:       --full-scan (lazy)")
        print(f"  Properties: {len(properties)}")
        print(f"  External API calls: 0 (all scans cached, updating derived columns only)")

    if needs_api and not _confirm_proceed(auto_approve):
        return

    print(f"\n[full-scan] {len(properties)} properties to process")

    success = 0
    for p in properties:
        label = p.get("address") or p["id"]
        lat, lng = p.get("latitude"), p.get("longitude")

        if not lat or not lng:
            print(f"  SKIP {label} -- missing lat/lng")
            continue

        work = _needs_work(p, force)
        work_items = [k for k, v in work.items() if v]
        print(f"  [{label}] needs: {', '.join(work_items)}")

        try:
            patch_data = {}

            # ── Only run API-heavy scans if neighborhood_scan is missing ──
            if work["scan"]:
                print(f"  [{label}] Running restaurant scan...")
                google_data, total_found = scrape_area(lat, lng)
                initial_ranked = opportunity_score(google_data)
                final_ranked = enrich_and_rank(initial_ranked, google_data, total_found, top_n=15)

                print(f"  [{label}] Running retail scan...")
                raw_market_data = {}
                for category in RETAIL_CATEGORIES:
                    raw_market_data[category] = search_nearby_retail(lat, lng, category)
                    time.sleep(0.05)
                retail_rankings = calculate_hub_aware_opportunity(raw_market_data)

                print(f"  [{label}] Running foot traffic scan...")
                foot_traffic_text = get_foot_traffic_analysis(lat, lng)

                print(f"  [{label}] Building neighborhood scan JSONB...")
                scan_json = build_neighborhood_scan(
                    restaurant_data=google_data,
                    restaurant_yelp=final_ranked,
                    retail_data=raw_market_data,
                )

                restaurant_text = _format_restaurant_text(final_ranked)
                retail_text = _format_retail_text(retail_rankings)

                patch_data["neighborhood_scan"] = scan_json
                if restaurant_text and restaurant_text.strip():
                    patch_data["restaurant_analysis"] = restaurant_text
                if retail_text and retail_text.strip():
                    patch_data["retail_analysis"] = retail_text
                if foot_traffic_text and foot_traffic_text.strip():
                    patch_data["foot_traffic_analysis"] = foot_traffic_text

            else:
                # Scan exists — reconstruct text columns from cached JSONB if needed
                scan_json = p["neighborhood_scan"]
                if isinstance(scan_json, str):
                    scan_json = json.loads(scan_json)

                if work["restaurant"]:
                    google_data, total_found, yelp_by_cat = reconstruct_restaurant_inputs(scan_json)
                    initial_ranked = opportunity_score(google_data)
                    final_ranked = []
                    for cat, initial_score, d in initial_ranked[:15]:
                        yelp = yelp_by_cat.get(cat)
                        h_score, m_share = calculate_hybrid_score(
                            cat, d, google_data, yelp, total_found
                        )
                        final_ranked.append({"cat": cat, "score": h_score, "share": m_share, "g": d, "y": yelp})
                    final_ranked.sort(key=lambda x: x["score"], reverse=True)
                    restaurant_text = _format_restaurant_text(final_ranked)
                    if restaurant_text and restaurant_text.strip():
                        patch_data["restaurant_analysis"] = restaurant_text

                if work["retail"]:
                    raw_market_data = reconstruct_retail_inputs(scan_json)
                    retail_rankings = calculate_hub_aware_opportunity(raw_market_data)
                    retail_text = _format_retail_text(retail_rankings)
                    if retail_text and retail_text.strip():
                        patch_data["retail_analysis"] = retail_text

                if work["foot_traffic"]:
                    foot_traffic_text = get_foot_traffic_analysis(lat, lng)
                    if foot_traffic_text and foot_traffic_text.strip():
                        patch_data["foot_traffic_analysis"] = foot_traffic_text

            # ── ML predictions (always from scan data, no API calls) ──
            if work["ml"]:
                print(f"  [{label}] Running ML predictions...")
                if isinstance(scan_json, str):
                    scan_json = json.loads(scan_json)
                ml_preds = _run_ml_predict(p, scan_json)
                if ml_preds is not None:
                    patch_data["ml_predictions"] = ml_preds

            # ── Write only changed columns ────────────────────────────
            if not patch_data:
                print(f"  SKIP {label} -- nothing to update")
                continue

            resp = requests.patch(
                f"{SUPABASE_URL}/rest/v1/properties?id=eq.{p['id']}",
                headers=HEADERS,
                json=patch_data,
            )
            resp.raise_for_status()
            success += 1
            print(f"  OK   {label} (updated: {', '.join(patch_data.keys())})")
        except Exception as e:
            print(f"  FAIL {label} -- {e}")

    print(f"[full-scan] Done: {success}/{len(properties)} succeeded")


def run_rescore(force: bool, dry_run: bool = False,
                limit: int = 1, auto_approve: bool = False,
                property_id: str | None = None):
    """
    Re-run scoring formulas against cached neighborhood_scan JSONB, no API calls.

    Reads the stored JSONB, reconstructs the inputs that the scoring functions
    expect (including review texts for retail friction), re-runs the formulas,
    and PATCHes the text analysis columns.
    """
    if dry_run:
        properties = _apply_limit(_DRY_RUN_PROPERTIES, limit)
        print(f"\n[rescore] [DRY-RUN] {len(properties)} sample properties")
        for p in properties:
            label = p.get("address") or p["id"]
            print(f"  [DRY-RUN] WOULD rescore {label}")
        print(f"[rescore] [DRY-RUN] Done: {len(properties)}/{len(properties)} (simulated)")
        return

    params = {"select": "id,address,latitude,longitude,neighborhood_scan"}
    if not force:
        params["neighborhood_scan"] = "not.is.null"
    if property_id:
        params["id"] = f"eq.{property_id}"

    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/properties", headers=HEADERS, params=params
    )
    if not resp.ok:
        sys.exit(f"Supabase error {resp.status_code}: {resp.text}")

    properties = resp.json()
    if not isinstance(properties, list):
        sys.exit(f"Unexpected response (expected list): {properties}")

    properties = _apply_limit(properties, limit)
    _preflight_summary("rescore", properties)

    print(f"\n[rescore] {len(properties)} properties to rescore")

    success = 0
    for p in properties:
        label = p.get("address") or p["id"]
        scan_data = p.get("neighborhood_scan")
        if not scan_data:
            print(f"  SKIP {label} -- no neighborhood_scan data")
            continue

        if isinstance(scan_data, str):
            scan_data = json.loads(scan_data)

        try:
            # ── Restaurant rescore ───────────────────────────────────
            google_data, total_found, yelp_by_cat = reconstruct_restaurant_inputs(scan_data)
            initial_ranked = opportunity_score(google_data)

            final_ranked = []
            for cat, initial_score, d in initial_ranked[:15]:
                yelp = yelp_by_cat.get(cat)
                h_score, m_share = calculate_hybrid_score(
                    cat, d, google_data, yelp, total_found
                )
                final_ranked.append({
                    "cat": cat,
                    "score": h_score,
                    "share": m_share,
                    "g": d,
                    "y": yelp,
                })

            final_ranked.sort(key=lambda x: x["score"], reverse=True)
            restaurant_text = _format_restaurant_text(final_ranked)

            # ── Retail rescore ───────────────────────────────────────
            raw_market_data = reconstruct_retail_inputs(scan_data)
            retail_rankings = calculate_hub_aware_opportunity(raw_market_data)
            retail_text = _format_retail_text(retail_rankings)

            # ── Foot traffic (free, recalculate live) ────────────────
            lat, lng = p.get("latitude"), p.get("longitude")
            foot_traffic_text = ""
            if lat and lng:
                foot_traffic_text = get_foot_traffic_analysis(lat, lng)

            # ── PATCH text columns ───────────────────────────────────
            patch_data = {}
            if restaurant_text and restaurant_text.strip():
                patch_data["restaurant_analysis"] = restaurant_text
            if retail_text and retail_text.strip():
                patch_data["retail_analysis"] = retail_text
            if foot_traffic_text and foot_traffic_text.strip():
                patch_data["foot_traffic_analysis"] = foot_traffic_text

            if not patch_data:
                print(f"  SKIP {label} -- rescore produced no output")
                continue

            resp = requests.patch(
                f"{SUPABASE_URL}/rest/v1/properties?id=eq.{p['id']}",
                headers=HEADERS,
                json=patch_data,
            )
            resp.raise_for_status()
            success += 1
            print(f"  OK   {label} (restaurant: {len(final_ranked)} cats, retail: {len(retail_rankings)} cats)")
        except Exception as e:
            print(f"  FAIL {label} -- {e}")

    print(f"[rescore] Done: {success}/{len(properties)} succeeded")


def main():
    parser = argparse.ArgumentParser(
        description="Back-populate analysis columns for properties."
    )
    parser.add_argument(
        "--types",
        nargs="+",
        choices=ALL_TYPES,
        default=ALL_TYPES,
        help="Which analysis types to run (default: all)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run even if the analysis column already has data",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the run using stub data; no APIs or database are called",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Max properties to process (default: 1). Use --limit 0 for all.",
    )
    parser.add_argument(
        "--property-id",
        type=str,
        help="Backfill only this property id (UUID)",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompt (use for scripted runs)",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--full-scan",
        action="store_true",
        help="Run all analyses + build neighborhood_scan JSONB for ML pipeline",
    )
    mode_group.add_argument(
        "--rescore",
        action="store_true",
        help="Re-run scoring formulas from cached JSONB (no API calls)",
    )
    mode_group.add_argument(
        "--predict",
        action="store_true",
        help="Run ML model from cached neighborhood_scan JSONB (no API calls)",
    )
    args = parser.parse_args()

    if not args.dry_run and (not SUPABASE_URL or not SUPABASE_KEY):
        sys.exit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

    if not args.dry_run:
        _check_db_connection()

    common = dict(limit=args.limit, auto_approve=args.yes, property_id=args.property_id)

    if args.full_scan:
        run_full_scan(args.force, dry_run=args.dry_run, **common)
    elif args.rescore:
        run_rescore(args.force, dry_run=args.dry_run, **common)
    elif args.predict:
        run_predict(args.force, dry_run=args.dry_run, **common)
    else:
        for t in args.types:
            if t == "ml":
                run_predict(args.force, dry_run=args.dry_run, **common)
            else:
                run_analysis(t, args.force, dry_run=args.dry_run, **common)

    if args.dry_run:
        print("\nDry run complete — no APIs were called and no data was written.")
    else:
        print("\nAll done.")


if __name__ == "__main__":
    main()
