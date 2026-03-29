-- Add JSONB column for raw neighborhood scan data (ML pipeline input).
-- This stores structured per-category scan results alongside the existing
-- TEXT analysis columns. The TEXT columns feed the LLM; this JSONB feeds
-- Ryan's ML model via get_ml_input().

alter table public.properties
  add column if not exists neighborhood_scan jsonb null;

comment on column public.properties.neighborhood_scan is
  'Raw structured scan data for ML pipeline. Serialized list of CategoryScan objects.';