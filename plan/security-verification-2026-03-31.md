# Security Verification (2026-03-31)

## Live DB checks (production via Supabase MCP)

- `public.property_images` now has `rls_enabled = true`.
- Only `SELECT` policies remain on exposed app tables:
  - `Public read properties`
  - `Public read recommendations`
  - `Public read property_images`
- `storage.objects` insert policy for public was removed.

## Anonymous access checks

- Allowed:
  - `anon` can `SELECT` from `public.public_properties_demo`.
  - `anon` can `SELECT` from `public.public_property_images_demo`.
- Blocked:
  - `anon` cannot `SELECT` from `public.properties`.
  - `anon` cannot `SELECT` from `public.property_images`.
  - `anon` cannot `SELECT` from `public.recommendations`.
  - `anon` cannot `INSERT` into `public.properties` / `public.recommendations` / `public.property_images`.
  - `anon` attempted `INSERT` into `storage.objects` fails with RLS violation.

## API/Code checks

- `backend/api/main.py` compiles under Python 3 (`python3 -m py_compile backend/api/main.py`).
- Generate endpoint now enforces:
  - one-time generation per property from public path (returns existing rows once present),
  - per-IP + per-property window throttling,
  - daily generation cap.
