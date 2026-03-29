import json
import time
from pathlib import Path

from . import config

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text()


def _format_ml_predictions(value) -> str:
    if value is None:
        return "Not provided"

    parsed = value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return "Not provided"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return raw

    if isinstance(parsed, list):
        if not parsed:
            return "Not provided"
        return json.dumps(parsed, separators=(",", ":"), sort_keys=True)

    if isinstance(parsed, dict):
        return json.dumps(parsed, separators=(",", ":"), sort_keys=True)

    text = str(parsed).strip()
    return text or "Not provided"


def _build_context(property_data: dict) -> dict:
    def _val(key, fmt=None):
        v = property_data.get(key)
        if v is None:
            return "Not provided"
        if fmt:
            return fmt(v)
        return str(v)

    return {
        "address": _val("address"),
        "city": _val("city"),
        "state_code": _val("state_code"),
        "square_footage": _val("square_footage"),
        "asking_rent_per_sqft": _val("asking_rent_per_sqft", lambda v: f"${v}"),
        "description": _val("description"),
        "restaurant_analysis": _val("restaurant_analysis"),
        "retail_analysis": _val("retail_analysis"),
        "foot_traffic_analysis": _val("foot_traffic_analysis"),
        "ml_predictions": _format_ml_predictions(property_data.get("ml_predictions")),
    }


def _run_reasoning(context: dict, openai_client) -> str:
    template = _load_prompt("reasoning.txt")
    try:
        prompt = template.format(**context)
    except Exception as exc:
        raise

    response = openai_client.chat.completions.create(
        model=config.REASONING_MODEL,
        max_completion_tokens=config.REASONING_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content
    return content


def _run_scoring(context: dict, reasoning_output: str, openai_client) -> list[dict]:
    template = _load_prompt("scoring.txt")
    prompt = template.format(**context, reasoning_output=reasoning_output)

    response = openai_client.chat.completions.create(
        model=config.SCORING_MODEL,
        temperature=config.SCORING_TEMPERATURE,
        max_tokens=config.SCORING_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    data = json.loads(response.choices[0].message.content)
    raw_recs = data.get("recommendations", [])

    validated = []
    for item in raw_recs:
        bt = item.get("business_type")
        score = item.get("score")
        reasoning = item.get("reasoning")

        if not isinstance(bt, str) or not bt:
            print(f"  WARNING: dropping item with invalid business_type: {item}")
            continue
        if not isinstance(score, int) or score < 1 or score > 100:
            print(f"  WARNING: dropping item with invalid score: {item}")
            continue
        if not isinstance(reasoning, str) or not reasoning:
            print(f"  WARNING: dropping item with missing reasoning: {item}")
            continue

        validated.append({
            "business_type": bt,
            "score": score,
            "reasoning": reasoning,
            "survival_probability": item.get("survival_probability"),
            "estimated_annual_revenue": item.get("estimated_annual_revenue"),
            "capture_rate": item.get("capture_rate"),
        })

    validated.sort(key=lambda x: x["score"], reverse=True)
    return validated


def _save_recommendations(property_id: str, recommendations: list[dict], supabase_client):
    supabase_client.table("recommendations").delete().eq(
        "property_id", property_id
    ).execute()

    rows = [
        {
            "property_id": property_id,
            "rank": i + 1,
            "business_type": rec["business_type"],
            "score": rec["score"],
            "reasoning": rec["reasoning"],
            "survival_probability": rec.get("survival_probability"),
            "estimated_annual_revenue": rec.get("estimated_annual_revenue"),
            "capture_rate": rec.get("capture_rate"),
        }
        for i, rec in enumerate(recommendations)
    ]

    supabase_client.table("recommendations").insert(rows).execute()


def generate_recommendations(
    property_id: str,
    supabase_client,
    openai_client,
    dry_run: bool = False,
) -> list[dict]:
    print(f"Fetching property {property_id}...")
    result = (
        supabase_client.table("properties")
        .select("*")
        .eq("id", property_id)
        .single()
        .execute()
    )
    property_data = result.data
    if not property_data:
        raise ValueError(f"Property {property_id} not found")

    missing = [
        col
        for col in (
            "restaurant_analysis",
            "retail_analysis",
            "foot_traffic_analysis",
            "ml_predictions",
        )
        if not property_data.get(col)
    ]
    if missing:
        raise ValueError(
            f"Property {property_id} is missing analyses: {', '.join(missing)}. "
            "Run the backfill script first."
        )

    context = _build_context(property_data)

    print("Running Step 1: Reasoning...")
    t0 = time.time()
    try:
        reasoning_output = _run_reasoning(context, openai_client)
    except Exception as exc:
        raise
    print(f"  Step 1 complete ({time.time() - t0:.1f}s)")

    print("Running Step 2: Scoring...")
    t0 = time.time()
    recommendations = _run_scoring(context, reasoning_output, openai_client)
    print(f"  Step 2 complete ({time.time() - t0:.1f}s)")
    print(f"  {len(recommendations)} business types scored")

    if not dry_run:
        _save_recommendations(property_id, recommendations, supabase_client)
        print(f"  Saved {len(recommendations)} rows to recommendations table")
    else:
        print("  Dry run — skipped DB write")

    return recommendations
