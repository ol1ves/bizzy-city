# BusiCity Frontend

AI-powered recommendations for what business to open at commercial properties in Manhattan. Built with Next.js, Google Maps, and Supabase.

## Getting Started

### Prerequisites

- Node.js 18+
- A Supabase project with the `properties` and `recommendations` tables (already deployed)
- A Google Cloud project with billing enabled

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Google Cloud API Setup

Enable these APIs in [Google Cloud Console → APIs & Services → Library](https://console.cloud.google.com/apis/library):

1. **Maps JavaScript API** — renders the interactive map
2. **Street View Static API** — provides building exterior images
3. **Places API** — already enabled if you followed earlier steps

### 3. Create a Map ID (required for styled pins)

1. Go to [Google Cloud Console → Google Maps Platform → Map Management](https://console.cloud.google.com/google/maps-apis/studio/maps)
2. Click **"Create Map ID"**
3. Name: `BusiCity` (or anything)
4. Map type: **JavaScript**
5. Rendering: **Raster** (not Vector)
6. Copy the Map ID → paste into `NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID` in `.env.local`

### 4. API Key Restrictions (recommended)

In Cloud Console → Credentials → your API key:
- **HTTP referrers:** `localhost:3000/*` for dev, your deployed domain for prod
- **API restrictions:** Maps JavaScript API, Street View Static API, Places API

### 5. Configure Environment

```bash
cp .env.local.example .env.local
```

Fill in your values:

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon/public key (NOT the service key) |
| `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` | Google Maps API key |
| `NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID` | Google Maps Map ID (see step 3) |

### 6. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Architecture

```
src/
├── app/                  # Next.js App Router
├── components/
│   ├── map/              # Map, pins, info windows
│   ├── detail/           # Property detail slide panel
│   └── ui/               # Reusable UI primitives
├── hooks/                # Data-fetching hooks
├── lib/                  # Supabase client, types, Street View utils
└── constants.ts          # Colors, map defaults
```

## Future Backend Integration

The "Generate Recommendations" button is currently disabled. It will call:

```
POST /api/recommendations/{property_id}
```

Response format:
```json
{
  "property_id": "uuid",
  "recommendations": [
    {
      "rank": 1,
      "business_type": "specialty coffee shop",
      "score": 92,
      "reasoning": "High foot traffic from office workers...",
      "demand_signals": {
        "yelp_gap": "Only 2 coffee shops in 3-block radius",
        "foot_traffic": "High — 12,000 daily pedestrians"
      }
    }
  ]
}
```

The FastAPI base URL will be stored as `NEXT_PUBLIC_API_URL`.
