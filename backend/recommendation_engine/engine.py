import json
import time
from pathlib import Path

from . import config

PROMPTS_DIR = Path(__file__).parent / "prompts"
_AGENT_LOG_PATH = Path("/Users/oliversantana/Documents/dev/busi-city/.cursor/debug-c6821a.log")


def _agent_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # region agent log
    try:
        payload = {
            "sessionId": "c6821a",
            "runId": "local-500",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        _AGENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _AGENT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str, separators=(",", ":")) + "\n")
    except Exception:
        pass
    # endregion


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


def _fallback_summary(rec: dict) -> str:
    return (
        f"This concept earned a {rec['score']}/100 fit score from demand, competition, "
        "foot traffic, space and rent feasibility, plus model-based signals. "
        "A detailed summary was unavailable — try regenerating recommendations."
    )


def _run_summaries(context: dict, recommendations: list[dict], openai_client) -> None:
    template = _load_prompt("summary.txt")
    if "{recommendations_json}" not in template:
        raise ValueError("summary.txt must contain {recommendations_json}")
    head, tail = template.split("{recommendations_json}", 1)
    payload = []
    for i, rec in enumerate(recommendations):
        payload.append({
            "rank": i + 1,
            "business_type": rec["business_type"],
            "score": rec["score"],
            "scoring_reasoning": rec["reasoning"],
            "survival_probability": rec.get("survival_probability"),
            "estimated_annual_revenue": rec.get("estimated_annual_revenue"),
            "capture_rate": rec.get("capture_rate"),
        })
    rec_json = json.dumps(payload, indent=2)
    prompt = head.format(**context) + rec_json + tail

    response = openai_client.chat.completions.create(
        model=config.SUMMARY_MODEL,
        temperature=config.SUMMARY_TEMPERATURE,
        max_tokens=config.SUMMARY_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    data = json.loads(raw)
    rows = data.get("summaries", [])
    by_type = {}
    for item in rows:
        bt = item.get("business_type")
        text = item.get("summary")
        if isinstance(bt, str) and isinstance(text, str) and text.strip():
            by_type[bt.strip()] = text.strip()

    for rec in recommendations:
        summary = by_type.get(rec["business_type"]) or by_type.get(
            rec["business_type"].strip()
        )
        rec["summary"] = summary if summary else _fallback_summary(rec)


def _save_recommendations(property_id: str, recommendations: list[dict], supabase_client):
    # region agent log
    _agent_log(
        "H1",
        "engine._save_recommendations:entry",
        "save_recommendations started",
        {"property_id": property_id, "row_count": len(recommendations)},
    )
    # endregion
    try:
        supabase_client.table("recommendations").delete().eq(
            "property_id", property_id
        ).execute()
    except Exception as exc:
        # region agent log
        _agent_log(
            "H1",
            "engine._save_recommendations:delete",
            "delete failed",
            {"error_type": type(exc).__name__, "error": str(exc)},
        )
        # endregion
        raise

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
            "summary": rec.get("summary"),
        }
        for i, rec in enumerate(recommendations)
    ]

    if rows:
        sample = rows[0]
        # region agent log
        _agent_log(
            "H2",
            "engine._save_recommendations:before_insert",
            "first row field types",
            {
                "types": {
                    k: type(v).__name__
                    for k, v in sample.items()
                },
            },
        )
        # endregion

    try:
        supabase_client.table("recommendations").insert(rows).execute()
    except Exception as exc:
        # region agent log
        _agent_log(
            "H1",
            "engine._save_recommendations:insert",
            "insert failed",
            {"error_type": type(exc).__name__, "error": str(exc)},
        )
        # endregion
        raise

    # region agent log
    _agent_log(
        "H1",
        "engine._save_recommendations:ok",
        "save_recommendations completed",
        {"property_id": property_id, "row_count": len(rows)},
    )
    # endregion


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

    print("Running Step 3: User summaries...")
    t0 = time.time()
    _run_summaries(context, recommendations, openai_client)
    print(f"  Step 3 complete ({time.time() - t0:.1f}s)")

    if not dry_run:
        _save_recommendations(property_id, recommendations, supabase_client)
        print(f"  Saved {len(recommendations)} rows to recommendations table")
    else:
        print("  Dry run — skipped DB write")

    # region agent log
    _agent_log(
        "H3",
        "engine.generate_recommendations:return",
        "returning recommendations to caller",
        {"count": len(recommendations)},
    )
    # endregion
    return recommendations
