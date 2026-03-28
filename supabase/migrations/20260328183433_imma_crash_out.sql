-- =============================================================
-- Migration: full_schema (no photos)
-- Target: Supabase (Postgres 15+)
-- =============================================================

CREATE EXTENSION IF NOT EXISTS "postgis";


-- 1. Properties
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS properties (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  crexi_id        text UNIQUE,
  crexi_url       text,
  address         text NOT NULL,
  city            text NOT NULL DEFAULT 'New York',
  neighborhood    text,
  zip_code        text,
  latitude        double precision,
  longitude       double precision,
  property_type   text,
  square_footage  integer,
  asking_rent     numeric(12,2),
  asking_rent_per_sqft  numeric(8,2),
  year_built      integer,
  listing_status  text DEFAULT 'active',
  broker_name     text,
  broker_company  text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);


-- 2. Recommendations
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS recommendations (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id     uuid NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  rank            integer NOT NULL,
  business_type   text NOT NULL,
  score           integer NOT NULL CHECK (score BETWEEN 1 AND 100),
  reasoning       text,
  demand_signals  jsonb DEFAULT '{}',
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);


-- 3. Indexes
-- ---------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_properties_neighborhood   ON properties (neighborhood);
CREATE INDEX IF NOT EXISTS idx_properties_zip             ON properties (zip_code);
CREATE INDEX IF NOT EXISTS idx_properties_type            ON properties (property_type);
CREATE INDEX IF NOT EXISTS idx_recommendations_property   ON recommendations (property_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_score      ON recommendations (score DESC);


-- 4. Auto-update trigger
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_properties_updated_at
  BEFORE UPDATE ON properties
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_recommendations_updated_at
  BEFORE UPDATE ON recommendations
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- 5. RLS — public read, service-role write
-- ---------------------------------------------------------
ALTER TABLE properties       ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendations  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read properties"      ON properties       FOR SELECT USING (true);
CREATE POLICY "Public read recommendations" ON recommendations  FOR SELECT USING (true);
CREATE POLICY "Service insert properties"      ON properties       FOR INSERT WITH CHECK (true);
CREATE POLICY "Service update properties"      ON properties       FOR UPDATE USING (true);
CREATE POLICY "Service insert recommendations" ON recommendations  FOR INSERT WITH CHECK (true);
CREATE POLICY "Service update recommendations" ON recommendations  FOR UPDATE USING (true);


-- 6. View: property + top recommendation
-- ---------------------------------------------------------
CREATE OR REPLACE VIEW properties_with_top_rec AS
SELECT
  p.*,
  r.business_type  AS top_rec_business,
  r.score          AS top_rec_score,
  r.reasoning      AS top_rec_reasoning
FROM properties p
LEFT JOIN LATERAL (
  SELECT business_type, score, reasoning
  FROM recommendations
  WHERE property_id = p.id
  ORDER BY rank ASC
  LIMIT 1
) r ON true;