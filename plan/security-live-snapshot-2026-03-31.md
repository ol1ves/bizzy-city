# Production Supabase Security Snapshot (2026-03-31)

Project: `klsragjgbrnuglqvjrbf` (`busi-city`)

## Live findings (MCP)

- `public.properties`: RLS enabled.
- `public.recommendations`: RLS enabled.
- `public.property_images`: RLS **disabled**.
- `storage.objects`: RLS enabled.
- `storage.buckets`: `property-photos` exists and is `public = true`.

### Public-facing policies discovered

- `public.properties`
  - `Public read properties` (`SELECT USING true`)
  - `Service insert properties` (`INSERT WITH CHECK true`)
  - `Service update properties` (`UPDATE USING true`)
- `public.recommendations`
  - `Public read recommendations` (`SELECT USING true`)
  - `Service insert recommendations` (`INSERT WITH CHECK true`)
  - `Service update recommendations` (`UPDATE USING true`)
- `storage.objects`
  - `Public read photos` (`SELECT` for `bucket_id = 'property-photos'`)
  - `Service upload photos` (`INSERT WITH CHECK bucket`)

### High-risk grants discovered

- `anon` and `authenticated` have broad table privileges (including write verbs) on:
  - `public.properties`
  - `public.recommendations`
  - `public.property_images`
  - `public.properties_with_top_rec`
  - storage tables including `storage.objects`

### View exposure

- `public.properties_with_top_rec` includes internal columns:
  - `restaurant_analysis`
  - `retail_analysis`
  - `foot_traffic_analysis`
  - `ml_predictions`
  - `top_rec_reasoning`

## Intended post-hardening state

- Public access: read-only and minimized to UI-needed columns via demo views.
- Public writes: blocked on all app tables and storage objects.
- Generation endpoint: public one-time generation per property only (first time), then read-only returns.
