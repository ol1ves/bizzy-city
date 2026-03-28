-- =============================================================
-- Migration: full_schema
-- Description: Complete schema for hackathon property gap-analysis app.
--              Tables: properties, property_photos, recommendations
--              Plus: storage bucket, indexes, RLS policies, triggers.
-- Target: Supabase (Postgres 15+)
-- =============================================================

-- 0. Extensions
-- ---------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "postgis";            -- for lat/lng if you want geo queries later


-- 1. Properties
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS properties (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Source identifiers
  crexi_id        text UNIQUE,
  crexi_url       text,

  -- Location
  address         text NOT NULL,
  city            text NOT NULL DEFAULT 'New York',
  neighborhood    text,
  zip_code        text,
  latitude        double precision,
  longitude       double precision,

  -- Listing details
  property_type   text,                              -- 'retail', 'restaurant', 'office', etc.
  square_footage  integer,
  asking_rent     numeric(12,2),                     -- total monthly ask
  asking_rent_per_sqft  numeric(8,2),
  year_built      integer,
  listing_status  text DEFAULT 'active',             -- active | leased | off_market

  -- Broker
  broker_name     text,
  broker_company  text,

  -- Timestamps
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE properties IS 'Commercial listings scraped/seeded from Crexi (Manhattan retail & restaurant).';


-- 2. Property Photos
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS property_photos (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id     uuid NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  storage_path    text NOT NULL,                     -- path inside the Supabase storage bucket
  public_url      text,                              -- full public URL after upload
  display_order   integer DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE property_photos IS 'References to images stored in the property-photos storage bucket.';


-- 3. Recommendations
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS recommendations (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id     uuid NOT NULL REFERENCES properties(id) ON DELETE CASCADE,

  -- Recommendation payload
  rank            integer NOT NULL,                  -- 1 = top pick, up to 10
  business_type   text NOT NULL,                     -- e.g. 'specialty coffee shop', 'urgent care clinic'
  score           integer NOT NULL CHECK (score BETWEEN 1 AND 100),
  reasoning       text,                              -- LLM-generated explanation
  demand_signals  jsonb DEFAULT '{}',                -- raw signal data (yelp gaps, reddit mentions, census, etc.)

  -- Timestamps
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE recommendations IS 'LLM-generated business recommendations per property, ranked 1-10 with scores.';


-- 4. Indexes
-- ---------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_properties_neighborhood   ON properties (neighborhood);
CREATE INDEX IF NOT EXISTS idx_properties_zip             ON properties (zip_code);
CREATE INDEX IF NOT EXISTS idx_properties_type            ON properties (property_type);
CREATE INDEX IF NOT EXISTS idx_photos_property            ON property_photos (property_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_property   ON recommendations (property_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_score      ON recommendations (score DESC);


-- 5. Auto-update updated_at trigger
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


-- 6. Storage bucket (run in Supabase dashboard SQL editor)
-- ---------------------------------------------------------
INSERT INTO storage.buckets (id, name, public)
VALUES ('property-photos', 'property-photos', true)
ON CONFLICT (id) DO NOTHING;


-- 7. Row Level Security
-- ---------------------------------------------------------
-- Public read for all three tables (hackathon = no auth needed)
ALTER TABLE properties       ENABLE ROW LEVEL SECURITY;
ALTER TABLE property_photos  ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendations  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read properties"      ON properties       FOR SELECT USING (true);
CREATE POLICY "Public read property_photos" ON property_photos  FOR SELECT USING (true);
CREATE POLICY "Public read recommendations" ON recommendations  FOR SELECT USING (true);

-- Service-role write (your ingest script uses the service key)
CREATE POLICY "Service insert properties"      ON properties       FOR INSERT WITH CHECK (true);
CREATE POLICY "Service update properties"      ON properties       FOR UPDATE USING (true);
CREATE POLICY "Service insert property_photos" ON property_photos  FOR INSERT WITH CHECK (true);
CREATE POLICY "Service insert recommendations" ON recommendations  FOR INSERT WITH CHECK (true);
CREATE POLICY "Service update recommendations" ON recommendations  FOR UPDATE USING (true);

-- Storage: allow public reads, service-role writes
CREATE POLICY "Public read photos"   ON storage.objects FOR SELECT USING (bucket_id = 'property-photos');
CREATE POLICY "Service upload photos" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'property-photos');


-- 8. Handy view: properties with top recommendation
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

COMMENT ON VIEW properties_with_top_rec IS 'Each property joined with its #1 recommendation. Useful for map pin tooltips.';