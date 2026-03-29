from __future__ import annotations

import os
import sys
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

_backend_root = Path(__file__).resolve().parent.parent
load_dotenv(_backend_root.parent / ".env")
sys.path.insert(0, str(_backend_root))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAI
from supabase import create_client, Client as SupabaseClient

from recommendation_engine import generate_recommendations

ANALYSIS_COLUMNS = (
    "restaurant_analysis",
    "retail_analysis",
    "foot_traffic_analysis",
    "ml_predictions",
)

_supabase: SupabaseClient | None = None
_openai: OpenAI | None = None
DEBUG_LOG_PATH = Path("/Users/oliversantana/Documents/dev/busi-city/.cursor/debug-7ec9cb.log")


def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": "7ec9cb",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, separators=(",", ":")) + "\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _supabase, _openai

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY must be set")

    _supabase = create_client(url, key)
    _openai = OpenAI()
    yield
    _supabase = None
    _openai = None


app = FastAPI(title="BusiCity API", lifespan=lifespan)

allowed_origins = ["http://localhost:3000"]
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "supabase_ready": _supabase is not None,
        "openai_ready": _openai is not None,
    }


@app.get("/api/recommendations/{property_id}")
async def get_recommendations(property_id: str):
    assert _supabase is not None and _openai is not None

    # 1. Fetch property
    prop_result = (
        _supabase.table("properties")
        .select("id, restaurant_analysis, retail_analysis, foot_traffic_analysis, ml_predictions")
        .eq("id", property_id)
        .maybe_single()
        .execute()
    )
    if not prop_result.data:
        raise HTTPException(status_code=404, detail="Property not found")

    property_data = prop_result.data

    # 2. Check for cached recommendations
    recs_result = (
        _supabase.table("recommendations")
        .select("*")
        .eq("property_id", property_id)
        .order("rank")
        .execute()
    )
    if recs_result.data:
        return {
            "property_id": property_id,
            "recommendations": recs_result.data,
        }

    # 3. Check analysis completeness
    missing = [col for col in ANALYSIS_COLUMNS if not property_data.get(col)]
    if missing:
        return JSONResponse(
            status_code=202,
            content={
                "property_id": property_id,
                "missing_analyses": missing,
            },
        )

    # 4. Generate via the engine (2-step LLM pipeline)
    try:
        recommendations = generate_recommendations(
            property_id=property_id,
            supabase_client=_supabase,
            openai_client=_openai,
        )
    except Exception as exc:
        # region agent log
        _debug_log(
            run_id="initial",
            hypothesis_id="H5",
            location="main.py:get_recommendations",
            message="Endpoint returned recommendation generation error",
            data={"property_id": property_id, "error_type": type(exc).__name__, "error": str(exc)},
        )
        # endregion
        raise HTTPException(
            status_code=500,
            detail=f"Recommendation generation failed: {exc}",
        )

    return {
        "property_id": property_id,
        "recommendations": recommendations,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
