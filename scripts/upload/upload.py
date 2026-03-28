"""
Upload LoopNet listings from listings.json → Supabase (properties + property_photos).

Run from this directory:
    uv run upload.py
    uv run upload.py --listings path/to/listings.json
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent


def find_dotenv() -> Path | None:
    """Walk up from HERE until we find a .env file."""
    for parent in [HERE, *HERE.parents]:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
    return None


_dotenv_path = find_dotenv()
if _dotenv_path:
    load_dotenv(_dotenv_path)
else:
    load_dotenv()  # fallback: try CWD / shell env

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
BUCKET = os.environ.get("STORAGE_BUCKET", "property-photos")

MAX_PHOTOS = 5
GEOCODE_DELAY = 1.1  # Nominatim policy: max 1 req/sec

# Headers that convince LoopNet's CDN to serve images
PHOTO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.loopnet.com/",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

_geolocator = Nominatim(user_agent="busi-city-uploader/1.0")
_last_geocode_time: float = 0.0


def geocode_address(
    address: str, city: str, state: str, zip_code: str
) -> tuple[float | None, float | None]:
    """Return (lat, lng) for the given address, or (None, None) on failure."""
    global _last_geocode_time

    query = f"{address}, {city}, {state} {zip_code}, USA"

    elapsed = time.monotonic() - _last_geocode_time
    if elapsed < GEOCODE_DELAY:
        time.sleep(GEOCODE_DELAY - elapsed)

    try:
        location = _geolocator.geocode(query, timeout=10)
        _last_geocode_time = time.monotonic()
        if location:
            return location.latitude, location.longitude
        log.warning("Geocode returned no results for: %s", query)
        return None, None
    except (GeocoderTimedOut, GeocoderServiceError) as exc:
        _last_geocode_time = time.monotonic()
        log.warning("Geocode error for '%s': %s", query, exc)
        return None, None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_property_row(listing: dict, lat: float | None, lng: float | None) -> dict:
    """Map a listings.json entry to the `properties` table columns."""
    row: dict = {
        "loopnet_id": listing["loopnet_id"],
        "loopnet_url": listing["loopnet_url"],
        "address": listing["address"],
        "city": listing["city"],
        "state": listing["state"],
        "zip_code": listing["zip_code"],
        "property_type": listing["property_type"],
        "square_footage": listing.get("square_footage"),
        "price_per_sqft_yr": listing.get("price_per_sqft_yr"),
        "year_built": listing.get("year_built"),
        "scraped_at": listing["scraped_at"],
        # listing_type dropped from schema (all listings are for_lease)
    }
    if lat is not None:
        row["lat"] = lat
    if lng is not None:
        row["lng"] = lng
    return row


def ext_from_url(url: str) -> str:
    lower = url.split("?")[0].lower()
    return ".png" if lower.endswith(".png") else ".jpg"


def content_type_for_ext(ext: str) -> str:
    return "image/png" if ext == ".png" else "image/jpeg"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload listings.json to Supabase.")
    parser.add_argument(
        "--listings",
        type=Path,
        default=HERE / "listings.json",
        help="Path to listings.json (default: ./listings.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    listings_file: Path = args.listings.resolve()

    if not listings_file.exists():
        log.error("listings.json not found at %s", listings_file)
        sys.exit(1)

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    listings: list[dict] = json.loads(listings_file.read_text())
    log.info("Loaded %d listings from %s", len(listings), listings_file)

    total_upserted = 0
    total_photos_uploaded = 0
    total_photos_skipped = 0
    total_errors = 0

    for listing in listings:
        loopnet_id = listing.get("loopnet_id", "?")
        try:
            # ----------------------------------------------------------
            # 1. Check if property already exists and has coordinates
            # ----------------------------------------------------------
            existing_props = (
                supabase.table("properties")
                .select("id, lat, lng")
                .eq("loopnet_id", loopnet_id)
                .execute()
            )
            existing_prop = existing_props.data[0] if existing_props.data else None

            if existing_prop and existing_prop.get("lat") and existing_prop.get("lng"):
                lat = float(existing_prop["lat"])
                lng = float(existing_prop["lng"])
                log.info("[%s] Using stored coordinates (%.6f, %.6f)", loopnet_id, lat, lng)
            else:
                lat, lng = geocode_address(
                    listing["address"], listing["city"], listing["state"], listing["zip_code"]
                )
                if lat is not None:
                    log.info("[%s] Geocoded → %.6f, %.6f", loopnet_id, lat, lng)
                else:
                    log.warning(
                        "[%s] Could not geocode address — lat/lng will be null", loopnet_id
                    )

            # ----------------------------------------------------------
            # 2. Upsert property row (always updates all fields)
            # ----------------------------------------------------------
            property_row = build_property_row(listing, lat, lng)
            result = (
                supabase.table("properties")
                .upsert(property_row, on_conflict="loopnet_id")
                .execute()
            )
            property_id: str = result.data[0]["id"]
            total_upserted += 1
            log.info("[%s] Upserted: %s, %s", loopnet_id, listing["address"], listing["city"])

            # ----------------------------------------------------------
            # 3. Delete existing photo rows so we re-sync cleanly
            #    (storage files are overwritten via upsert: true)
            # ----------------------------------------------------------
            supabase.table("property_photos").delete().eq("property_id", property_id).execute()

            # ----------------------------------------------------------
            # 4. Upload photos (up to MAX_PHOTOS)
            # ----------------------------------------------------------
            photo_urls: list[str] = listing.get("photo_urls") or []
            for sort_order, url in enumerate(photo_urls[:MAX_PHOTOS]):
                try:
                    response = httpx.get(
                        url,
                        headers=PHOTO_HEADERS,
                        timeout=15,
                        follow_redirects=True,
                    )
                    if response.status_code != 200:
                        log.warning(
                            "[%s] Photo %d download failed (HTTP %d) — skipping",
                            loopnet_id,
                            sort_order,
                            response.status_code,
                        )
                        total_photos_skipped += 1
                        continue

                    image_bytes = response.content
                    ext = ext_from_url(url)
                    storage_path = f"{loopnet_id}/{sort_order}{ext}"

                    supabase.storage.from_(BUCKET).upload(
                        path=storage_path,
                        file=image_bytes,
                        file_options={
                            "content-type": content_type_for_ext(ext),
                            "upsert": "true",
                        },
                    )

                    public_url: str = supabase.storage.from_(BUCKET).get_public_url(storage_path)

                    supabase.table("property_photos").insert(
                        {
                            "property_id": property_id,
                            "storage_path": storage_path,
                            "public_url": public_url,
                            "sort_order": sort_order,
                        }
                    ).execute()

                    total_photos_uploaded += 1
                    log.info(
                        "[%s] Photo %d uploaded → %s/%s",
                        loopnet_id,
                        sort_order,
                        BUCKET,
                        storage_path,
                    )

                except Exception as photo_err:
                    log.warning(
                        "[%s] Photo %d error: %s — skipping", loopnet_id, sort_order, photo_err
                    )
                    total_photos_skipped += 1

        except Exception as err:
            log.error("[%s] Listing error: %s", loopnet_id, err)
            total_errors += 1

    print()
    print("=== Upload Complete ===")
    print(f"Properties upserted : {total_upserted}")
    print(f"Photos uploaded     : {total_photos_uploaded}")
    print(f"Photos skipped      : {total_photos_skipped}")
    print(f"Errors              : {total_errors}")


if __name__ == "__main__":
    main()
