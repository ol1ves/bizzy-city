# BizzyCity Frontend

Next.js 16 frontend for browsing commercial properties and viewing/generating AI business recommendations.

## Prerequisites

- Node.js 20+
- npm
- Google Cloud project with Maps APIs enabled
- Supabase project credentials for anon read access

## Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local
```

Configure `.env.local` values:

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon/public key |
| `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` | Google Maps JavaScript API key |
| `NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID` | Google Maps Map ID |
| `NEXT_PUBLIC_API_URL` | Backend origin (optional, defaults to `http://localhost:8000`) |

## Run

```bash
npm run dev
```

App runs on `http://localhost:3000`.

## Data Sources

- Property list: `public.public_properties_demo`
- Property images: `public.public_property_images_demo`
- Recommendations API: `GET /api/recommendations/{property_id}?generate=true|false`

## Structure

```text
src/
├── app/                  # App Router entry
├── components/
│   ├── map/              # Map and marker UI
│   ├── detail/           # Property panel and recommendations section
│   └── ui/               # Reusable UI primitives
├── hooks/                # Data-fetching hooks (Supabase + backend)
├── lib/                  # Supabase client, display helpers, types
└── constants.ts          # App constants
```

## Maps Setup Notes

Enable in Google Cloud:

- Maps JavaScript API
- Street View Static API
- Places API

For local development, restrict API key referrers to `localhost:3000/*`.

