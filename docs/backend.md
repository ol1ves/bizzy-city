# Backend API (FastAPI)

FastAPI backend for BizzyCity recommendation generation and API delivery.

## What This Service Does

- Exposes health endpoint: `GET /api/health`
- Exposes recommendation endpoint: `GET /api/recommendations/{property_id}`
- Reads/writes Supabase data using service-role credentials
- Generates recommendation outputs through the recommendation engine and OpenAI

## Requirements

- Python 3.11+
- Environment variables configured at repo root in `.env`

## Setup

From repository root:

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Alternative dependency source (same package set) exists in:

- `backend/requirements.txt`
- `backend/pyproject.toml`

## Environment Variables

Required:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `OPENAI_API_KEY`

Optional:

- `FRONTEND_URL` (added to CORS allowlist alongside `http://localhost:3000`)
- `DEMO_GENERATE_WINDOW_SECONDS` (default `300`)
- `DEMO_GENERATE_MAX_ATTEMPTS` (default `3`)
- `DEMO_DAILY_GENERATION_CAP` (default `250`)

## Run Locally

From repository root:

```bash
.venv/bin/python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

Open API docs at `http://localhost:8000/docs`.

## API Behavior

### `GET /api/health`

Returns readiness status for in-memory clients:

- `status`
- `supabase_ready`
- `openai_ready`

### `GET /api/recommendations/{property_id}?generate=true|false`

Behavior summary:

- `404` if property does not exist
- Returns cached recommendations immediately if already present
- `202` with `missing_analyses` if required analysis fields are absent
- If `generate=false`, returns read-only payload without generating
- Applies anti-abuse controls:
  - rate limit window per `(client_ip, property_id)`
  - daily generation cap
  - per-property in-process lock to prevent duplicate generation races
- `429` when throttled or daily cap is exceeded
- `500` if generation fails unexpectedly

Response shape includes:

- `property_id`
- `recommendations`
- `already_generated` (when applicable)

## Related Files

- API entrypoint: `backend/api/main.py`
- Recommendation pipeline: `backend/recommendation_engine/engine.py`
- ML interface helpers: `backend/ml_interface.py`
- Deploy start command reference:
  - `Procfile`
  - `railpack.json`

