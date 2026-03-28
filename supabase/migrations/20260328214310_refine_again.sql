-- Refine properties: state_code replaces neighborhood; drop year_built;
-- rename desire_* analysis to restaurant_*; add retail and foot-traffic analysis slots.
-- *_analyzed_at is maintained automatically when the matching *_analysis text changes.
--
-- PostgreSQL: RENAME COLUMN cannot be combined with other ALTER subcommands in one statement.

ALTER TABLE properties
  DROP COLUMN IF EXISTS neighborhood,
  ADD COLUMN IF NOT EXISTS state_code text NOT NULL DEFAULT 'NY',
  DROP COLUMN IF EXISTS year_built;

ALTER TABLE properties
  RENAME COLUMN desire_analysis TO restaurant_analysis;

ALTER TABLE properties
  RENAME COLUMN desire_analyzed_at TO restaurant_analyzed_at;

ALTER TABLE properties
  ADD COLUMN IF NOT EXISTS retail_analysis text,
  ADD COLUMN IF NOT EXISTS retail_analyzed_at timestamptz,
  ADD COLUMN IF NOT EXISTS foot_traffic_analysis text,
  ADD COLUMN IF NOT EXISTS foot_traffic_analyzed_at timestamptz;

COMMENT ON COLUMN properties.restaurant_analysis IS 'Cached restaurant-focused gap analysis (e.g. Google Places + Yelp). Fed to LLM for recommendations.';
COMMENT ON COLUMN properties.restaurant_analyzed_at IS 'Set automatically when restaurant_analysis changes. NULL = no analysis.';
COMMENT ON COLUMN properties.retail_analysis IS 'Cached retail gap analysis text.';
COMMENT ON COLUMN properties.retail_analyzed_at IS 'Set automatically when retail_analysis changes.';
COMMENT ON COLUMN properties.foot_traffic_analysis IS 'Cached foot-traffic analysis text.';
COMMENT ON COLUMN properties.foot_traffic_analyzed_at IS 'Set automatically when foot_traffic_analysis changes.';

-- Legacy rows: had text but no timestamp
UPDATE properties
SET restaurant_analyzed_at = now()
WHERE restaurant_analysis IS NOT NULL
  AND btrim(restaurant_analysis) <> ''
  AND restaurant_analyzed_at IS NULL;

CREATE OR REPLACE FUNCTION properties_sync_analysis_timestamps()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF NEW.restaurant_analysis IS DISTINCT FROM OLD.restaurant_analysis THEN
      NEW.restaurant_analyzed_at := CASE
        WHEN NEW.restaurant_analysis IS NULL THEN NULL
        WHEN btrim(NEW.restaurant_analysis) = '' THEN NULL
        ELSE now()
      END;
    END IF;
    IF NEW.retail_analysis IS DISTINCT FROM OLD.retail_analysis THEN
      NEW.retail_analyzed_at := CASE
        WHEN NEW.retail_analysis IS NULL THEN NULL
        WHEN btrim(NEW.retail_analysis) = '' THEN NULL
        ELSE now()
      END;
    END IF;
    IF NEW.foot_traffic_analysis IS DISTINCT FROM OLD.foot_traffic_analysis THEN
      NEW.foot_traffic_analyzed_at := CASE
        WHEN NEW.foot_traffic_analysis IS NULL THEN NULL
        WHEN btrim(NEW.foot_traffic_analysis) = '' THEN NULL
        ELSE now()
      END;
    END IF;
  ELSIF TG_OP = 'INSERT' THEN
    IF NEW.restaurant_analysis IS NOT NULL AND btrim(NEW.restaurant_analysis) <> '' THEN
      NEW.restaurant_analyzed_at := now();
    END IF;
    IF NEW.retail_analysis IS NOT NULL AND btrim(NEW.retail_analysis) <> '' THEN
      NEW.retail_analyzed_at := now();
    END IF;
    IF NEW.foot_traffic_analysis IS NOT NULL AND btrim(NEW.foot_traffic_analysis) <> '' THEN
      NEW.foot_traffic_analyzed_at := now();
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_properties_analysis_timestamps ON properties;
CREATE TRIGGER trg_properties_analysis_timestamps
  BEFORE INSERT OR UPDATE ON properties
  FOR EACH ROW EXECUTE FUNCTION properties_sync_analysis_timestamps();

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
