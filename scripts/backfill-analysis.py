"""
backfill-analysis.py
────────────────────
Back-populate analysis columns for properties in Supabase.

Supports three analysis types: restaurant, retail, foot_traffic.
Only processes properties where the relevant column is NULL or empty,
unless --force is passed.

Usage:
    python backfill-analysis.py                        # run all three
    python backfill-analysis.py --types restaurant     # restaurant only
    python backfill-analysis.py --types retail foot_traffic
    python backfill-analysis.py --force                # re-analyze everything
    python backfill-analysis.py --dry-run              # simulate with stub data, no APIs called

Env vars (loaded from ../.env):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
    GOOGLE_API_KEY
    SERPAPI_KEY
"""

import os
import sys
import argparse
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from RestaurantAnalysis import get_restaurant_analysis
from RetailAnalysis import get_retail_analysis
from FootTraffic import get_foot_traffic_analysis

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
    args = parser.parse_args()

    if not args.dry_run and (not SUPABASE_URL or not SUPABASE_KEY):
        sys.exit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

    for t in args.types:
        run_analysis(t, args.force, dry_run=args.dry_run)

    if args.dry_run:
        print("\nDry run complete — no APIs were called and no data was written.")
    else:
        print("\nAll done.")


if __name__ == "__main__":
    main()
