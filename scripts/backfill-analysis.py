"""
backfill-analysis.py
────────────────────
Back-populate analysis columns for properties in Supabase.

Supports three analysis types: restaurant, retail, foot_traffic.
Only processes properties where the relevant column is NULL or empty,
unless --force is passed.

--full-scan runs all three analyses PLUS builds the neighborhood_scan JSONB
for the ML pipeline, writing all four columns in a single PATCH per property.

Usage:
    python backfill-analysis.py                        # run all three (text only)
    python backfill-analysis.py --types restaurant     # restaurant only
    python backfill-analysis.py --types retail foot_traffic
    python backfill-analysis.py --force                # re-analyze everything
    python backfill-analysis.py --dry-run              # simulate with stub data, no APIs called
    python backfill-analysis.py --full-scan             # all analyses + JSONB
    python backfill-analysis.py --rescore               # re-run formulas from cached JSONB (no API calls)

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
from RestaurantAnalysis.FullAPIPull import scrape_area, opportunity_score, enrich_and_rank, calculate_hybrid_score
from RetailAnalysis import get_retail_analysis
from RetailAnalysis.RetailAPIPull import CATEGORIES as RETAIL_CATEGORIES, search_nearby_retail, calculate_hub_aware_opportunity
from FootTraffic import get_foot_traffic_analysis
from neighborhood_scan import (
    build_neighborhood_scan,
    build_foot_traffic,
    reconstruct_restaurant_inputs,
    reconstruct_retail_inputs,
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

ALL_TYPES = ["restaurant", "retail", "foot_traffic"]

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


def fetch_properties(column: str, force: bool) -> list:
    params = {"select": f"id,address,latitude,longitude,{column}"}
    if not force:
        params["or"] = f"({column}.is.null,{column}.eq.)"

    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/properties", headers=HEADERS, params=params
    )
    if not resp.ok:
        sys.exit(f"Supabase error {resp.status_code}: {resp.text}")

    data = resp.json()
    if not isinstance(data, list):
        sys.exit(f"Unexpected response (expected list): {data}")
    return data


def run_analysis(analysis_type: str, force: bool, dry_run: bool = False):
    cfg = ANALYSIS_MAP[analysis_type]
    column = cfg["column"]
    analyze = cfg["fn"]

    if dry_run:
        properties = _DRY_RUN_PROPERTIES
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

    properties = fetch_properties(column, force)
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


def fetch_properties_for_scan(force: bool) -> list:
    """Fetch properties that need a full neighborhood scan."""
    params = {"select": "id,address,latitude,longitude,neighborhood_scan"}
    if not force:
        params["neighborhood_scan"] = "is.null"

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


def run_full_scan(force: bool, dry_run: bool = False):
    """Run all three analyses + JSONB assembly, writing 4 columns per property."""
    if dry_run:
        properties = _DRY_RUN_PROPERTIES
        print(f"\n[full-scan] [DRY-RUN] {len(properties)} sample properties")
        for p in properties:
            label = p.get("address") or p["id"]
            print(f"  [DRY-RUN] WOULD run restaurant + retail + foot_traffic + JSONB for {label}")
        print(f"[full-scan] [DRY-RUN] Done: {len(properties)}/{len(properties)} (simulated)")
        return

    properties = fetch_properties_for_scan(force)
    print(f"\n[full-scan] {len(properties)} properties to process")

    success = 0
    for p in properties:
        label = p.get("address") or p["id"]
        lat, lng = p.get("latitude"), p.get("longitude")

        if not lat or not lng:
            print(f"  SKIP {label} -- missing lat/lng")
            continue

        if not force and p.get("neighborhood_scan"):
            print(f"  SKIP {label} -- already has neighborhood_scan")
            continue

        try:
            # ── Restaurant scan (Google + Yelp) ──────────────────────
            print(f"  [{label}] Running restaurant scan...")
            google_data, total_found = scrape_area(lat, lng)
            initial_ranked = opportunity_score(google_data)
            final_ranked = enrich_and_rank(initial_ranked, google_data, total_found, top_n=15)
            restaurant_text = _format_restaurant_text(final_ranked)

            # ── Retail scan (Google only) ────────────────────────────
            print(f"  [{label}] Running retail scan...")
            raw_market_data = {}
            for category in RETAIL_CATEGORIES:
                raw_market_data[category] = search_nearby_retail(lat, lng, category)
                time.sleep(0.05)

            retail_rankings = calculate_hub_aware_opportunity(raw_market_data)
            retail_text = _format_retail_text(retail_rankings)

            # ── Foot traffic (property location) ─────────────────────
            print(f"  [{label}] Running foot traffic scan...")
            foot_traffic_text = get_foot_traffic_analysis(lat, lng)

            # ── Build JSONB ──────────────────────────────────────────
            print(f"  [{label}] Building neighborhood scan JSONB...")
            scan_json = build_neighborhood_scan(
                restaurant_data=google_data,
                restaurant_yelp=final_ranked,
                retail_data=raw_market_data,
            )

            # ── Write all 4 columns in one PATCH ─────────────────────
            patch_data = {
                "neighborhood_scan": json.dumps(scan_json),
            }
            if restaurant_text and restaurant_text.strip():
                patch_data["restaurant_analysis"] = restaurant_text
            if retail_text and retail_text.strip():
                patch_data["retail_analysis"] = retail_text
            if foot_traffic_text and foot_traffic_text.strip():
                patch_data["foot_traffic_analysis"] = foot_traffic_text

            resp = requests.patch(
                f"{SUPABASE_URL}/rest/v1/properties?id=eq.{p['id']}",
                headers=HEADERS,
                json=patch_data,
            )
            resp.raise_for_status()
            success += 1
            n_cats = len(scan_json)
            n_biz = sum(len(s.get("businesses", [])) for s in scan_json)
            print(f"  OK   {label} ({n_cats} categories, {n_biz} businesses)")
        except Exception as e:
            print(f"  FAIL {label} -- {e}")

    print(f"[full-scan] Done: {success}/{len(properties)} succeeded")


def run_rescore(force: bool, dry_run: bool = False):
    """
    Re-run scoring formulas against cached neighborhood_scan JSONB, no API calls.

    Reads the stored JSONB, reconstructs the inputs that the scoring functions
    expect (including review texts for retail friction), re-runs the formulas,
    and PATCHes the text analysis columns.
    """
    if dry_run:
        properties = _DRY_RUN_PROPERTIES
        print(f"\n[rescore] [DRY-RUN] {len(properties)} sample properties")
        for p in properties:
            label = p.get("address") or p["id"]
            print(f"  [DRY-RUN] WOULD rescore {label}")
        print(f"[rescore] [DRY-RUN] Done: {len(properties)}/{len(properties)} (simulated)")
        return

    params = {"select": "id,address,latitude,longitude,neighborhood_scan"}
    if not force:
        params["neighborhood_scan"] = "not.is.null"

    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/properties", headers=HEADERS, params=params
    )
    if not resp.ok:
        sys.exit(f"Supabase error {resp.status_code}: {resp.text}")

    properties = resp.json()
    if not isinstance(properties, list):
        sys.exit(f"Unexpected response (expected list): {properties}")

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
    args = parser.parse_args()

    if not args.dry_run and (not SUPABASE_URL or not SUPABASE_KEY):
        sys.exit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

    if args.full_scan:
        run_full_scan(args.force, dry_run=args.dry_run)
    elif args.rescore:
        run_rescore(args.force, dry_run=args.dry_run)
    else:
        for t in args.types:
            run_analysis(t, args.force, dry_run=args.dry_run)

    if args.dry_run:
        print("\nDry run complete — no APIs were called and no data was written.")
    else:
        print("\nAll done.")


if __name__ == "__main__":
    main()
