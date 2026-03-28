"""
backfill_desire.py
──────────────────
Loops through properties in Supabase, calls get_desire_analysis() for each,
and writes the result back into the restaurant_analysis column (timestamps are set by the DB trigger).

Usage:
    python backfill_desire.py

    # Re-analyze properties that already have data:
    python backfill_desire.py --force

Env vars:
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
"""

import os
import sys
import argparse
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from DesireAnalysis.DesireAnalysis import get_desire_analysis

parser = argparse.ArgumentParser()
parser.add_argument("--force", action="store_true", help="Re-run even if restaurant_analysis already exists")
args = parser.parse_args()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    sys.exit("❌ SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env or the environment.")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def main():
    params = {"select": "id,address,latitude,longitude,restaurant_analysis"}
    if not args.force:
        # Catch both NULL and previously-written empty strings
        params["or"] = "(restaurant_analysis.is.null,restaurant_analysis.eq.)"

    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/properties", headers=HEADERS, params=params
    )

    if not resp.ok:
        sys.exit(f"❌ Supabase error {resp.status_code}: {resp.text}")

    properties = resp.json()

    if not isinstance(properties, list):
        sys.exit(f"❌ Unexpected response (expected list, got {type(properties).__name__}): {properties}")

    print(f"📦 {len(properties)} properties to process\n")

    for p in properties:
        label = p.get("address") or p["id"]
        lat, lng = p.get("latitude"), p.get("longitude")

        if not lat or not lng:
            print(f"  ⚠ {label} — missing lat/lng, skipping")
            continue

        try:
            result = get_desire_analysis(lat, lng)
            if not result or not result.strip():
                print(f"  ⚠ {label} — analysis returned empty (API quota hit or no businesses in radius?), skipping")
                continue
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/properties?id=eq.{p['id']}",
                headers=HEADERS,
                json={"restaurant_analysis": result},
            ).raise_for_status()
            print(f"  ✓ {label}")
        except Exception as e:
            print(f"  ✗ {label} — {e}")

    print("\n✅ Done.")


if __name__ == "__main__":
    main()