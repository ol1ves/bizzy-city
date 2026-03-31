from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

_backend_root = Path(__file__).resolve().parent.parent
load_dotenv(_backend_root.parent / ".env")
sys.path.insert(0, str(_backend_root))

from fastapi import FastAPI, HTTPException, Query, Request
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
_generation_locks: dict[str, asyncio.Lock] = {}
_generation_attempts: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_daily_generation_counts: dict[str, int] = defaultdict(int)

_WINDOW_SECONDS = int(os.getenv("DEMO_GENERATE_WINDOW_SECONDS", "300"))
_MAX_ATTEMPTS_PER_WINDOW = int(os.getenv("DEMO_GENERATE_MAX_ATTEMPTS", "3"))
_DAILY_GENERATION_CAP = int(os.getenv("DEMO_DAILY_GENERATION_CAP", "250"))

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


def _prune_and_count_attempts(client_ip: str, property_id: str) -> int:
    now = time.time()
    key = (client_ip, property_id)
    q = _generation_attempts[key]
    while q and now - q[0] > _WINDOW_SECONDS:
        q.popleft()
    return len(q)


def _register_attempt(client_ip: str, property_id: str) -> int:
    key = (client_ip, property_id)
    q = _generation_attempts[key]
    q.append(time.time())
    return len(q)


def _property_lock(property_id: str) -> asyncio.Lock:
    lock = _generation_locks.get(property_id)
    if lock is None:
        lock = asyncio.Lock()
        _generation_locks[property_id] = lock
    return lock


def _daily_key() -> str:
    return date.today().isoformat()


def _get_daily_count() -> int:
    return _daily_generation_counts[_daily_key()]


def _increment_daily_count() -> int:
    k = _daily_key()
    _daily_generation_counts[k] += 1
    return _daily_generation_counts[k]


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
async def get_recommendations(
    request: Request,
    property_id: str,
    generate: bool = Query(default=True, description="Generate recommendations when missing"),
):
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

    def _read_recommendations():
        return (
            _supabase.table("recommendations")
            .select("*")
            .eq("property_id", property_id)
            .order("rank")
            .execute()
        )

    # 2. Check for cached recommendations
    recs_result = _read_recommendations()
    if recs_result.data:
        return {
            "property_id": property_id,
            "recommendations": recs_result.data,
            "already_generated": True,
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

    # 4. Read-only mode: return empty recommendations without generating.
    if not generate:
        return {
            "property_id": property_id,
            "recommendations": [],
        }

    client_ip = request.client.host if request.client else "unknown"
    existing_attempts = _prune_and_count_attempts(client_ip, property_id)
    if existing_attempts >= _MAX_ATTEMPTS_PER_WINDOW:
        _agent_log(
            "SEC_RATE",
            "main.get_recommendations:rate_limited",
            "generation blocked by window throttle",
            {
                "property_id": property_id,
                "client_ip": client_ip,
                "attempts_in_window": existing_attempts,
                "window_seconds": _WINDOW_SECONDS,
            },
        )
        raise HTTPException(
            status_code=429,
            detail="Generation is temporarily rate limited for this property. Please try again shortly.",
        )
    _register_attempt(client_ip, property_id)

    daily_count = _get_daily_count()
    if daily_count >= _DAILY_GENERATION_CAP:
        _agent_log(
            "SEC_CAP",
            "main.get_recommendations:daily_cap",
            "generation blocked by daily cap",
            {
                "property_id": property_id,
                "client_ip": client_ip,
                "daily_count": daily_count,
                "daily_cap": _DAILY_GENERATION_CAP,
            },
        )
        raise HTTPException(
            status_code=429,
            detail="Daily generation limit reached for the demo.",
        )

    lock = _property_lock(property_id)
    async with lock:
        recs_result = _read_recommendations()
        if recs_result.data:
            _agent_log(
                "SEC_EXISTS",
                "main.get_recommendations:skip_existing",
                "generation skipped because recommendations already exist",
                {"property_id": property_id, "client_ip": client_ip},
            )
            return {
                "property_id": property_id,
                "recommendations": recs_result.data,
                "already_generated": True,
                "generation_blocked": "already_exists",
            }

    # 5. Generate via the engine (2-step LLM pipeline)
    try:
        async with lock:
            recs_result = _read_recommendations()
            if recs_result.data:
                return {
                    "property_id": property_id,
                    "recommendations": recs_result.data,
                    "already_generated": True,
                    "generation_blocked": "already_exists",
                }
            recommendations = generate_recommendations(
                property_id=property_id,
                supabase_client=_supabase,
                openai_client=_openai,
            )
    except Exception as exc:
        # region agent log
        _agent_log(
            "H4",
            "main.get_recommendations:exception",
            "generate_recommendations raised",
            {
                "property_id": property_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        # endregion
        raise HTTPException(
            status_code=500,
            detail=f"Recommendation generation failed: {exc}",
        )
    _increment_daily_count()

    # region agent log
    _agent_log(
        "H3",
        "main.get_recommendations:before_return",
        "preparing JSON response",
        {
            "property_id": property_id,
            "count": len(recommendations),
            "first_keys": list(recommendations[0].keys()) if recommendations else [],
        },
    )
    # endregion

    return {
        "property_id": property_id,
        "recommendations": recommendations,
        "already_generated": False,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
