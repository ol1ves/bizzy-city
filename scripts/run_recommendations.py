import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Import third-party packages BEFORE inserting project root into sys.path,
# to prevent the local supabase/ migrations directory from shadowing the PyPI package.
from openai import OpenAI
from supabase import create_client

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.recommendation_engine import generate_recommendations


def _print_table(recommendations: list[dict]):
    type_width = max(
        (len(r["business_type"]) for r in recommendations),
        default=20,
    )
    type_width = max(type_width, 13)
    reason_width = 50

    header = (
        f"{'Rank':<5} | {'Score':<5} | "
        f"{'Business Type':<{type_width}} | {'Reasoning':<{reason_width}}"
    )
    separator = "-" * len(header)

    print(f"\n{separator}")
    print(header)
    print(separator)

    for i, rec in enumerate(recommendations, 1):
        reasoning = rec["reasoning"]
        if len(reasoning) > reason_width:
            reasoning = reasoning[: reason_width - 3] + "..."
        print(
            f"{i:<5} | {rec['score']:<5} | "
            f"{rec['business_type']:<{type_width}} | {reasoning:<{reason_width}}"
        )

    print(separator)


def main():
    parser = argparse.ArgumentParser(
        description="Generate business-type recommendations for a property."
    )
    parser.add_argument(
        "property_id", nargs="?", help="UUID of a single property to analyze"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_properties",
        help="Re-run recommendations for every property in the DB (overwrites existing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the LLM pipeline but do not write results to the database",
    )
    args = parser.parse_args()

    if args.all_properties and args.property_id:
        raise SystemExit("Provide either a property_id or --all, not both.")
    if not args.all_properties and not args.property_id:
        raise SystemExit("Provide a property_id or pass --all.")

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY must be set in .env")

    supabase = create_client(supabase_url, supabase_key)
    openai = OpenAI()

    if args.all_properties:
        result = supabase.table("properties").select("id, address").execute()
        properties = result.data
        total = len(properties)
        succeeded = 0
        skipped = 0

        print(f"Found {total} properties. Running recommendations for all...\n")

        for idx, prop in enumerate(properties, 1):
            label = prop.get("address") or prop["id"]
            print(f"[{idx}/{total}] {label}")
            try:
                recs = generate_recommendations(
                    property_id=prop["id"],
                    supabase_client=supabase,
                    openai_client=openai,
                    dry_run=args.dry_run,
                )
                _print_table(recs)
                succeeded += 1
            except ValueError as e:
                print(f"  SKIPPED: {e}")
                if "ml_predictions" in str(e):
                    print("  Hint: run the ML backfill first so properties.ml_predictions is populated.")
                skipped += 1

        print(f"\nDone. {succeeded} succeeded, {skipped} skipped out of {total}.")
        if args.dry_run:
            print("Dry run — results were NOT saved to the database.")
    else:
        recommendations = generate_recommendations(
            property_id=args.property_id,
            supabase_client=supabase,
            openai_client=openai,
            dry_run=args.dry_run,
        )

        _print_table(recommendations)

        if args.dry_run:
            print("\nDry run — results were NOT saved to the database.")


if __name__ == "__main__":
    main()
