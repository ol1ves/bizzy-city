-- Migration: add_desire_analysis
-- Stores cached output from the Google Places + Yelp gap analysis algorithm.
-- One text blob per property so the LLM layer never needs to hit those APIs.

ALTER TABLE properties
ADD COLUMN IF NOT EXISTS desire_analysis text,
ADD COLUMN IF NOT EXISTS desire_analyzed_at timestamptz;

COMMENT ON COLUMN properties.desire_analysis IS 'Cached neighborhood gap-analysis output from FullAPIPull (Google Places + Yelp). Fed to LLM for recommendations.';
COMMENT ON COLUMN properties.desire_analyzed_at IS 'When the desire analysis was last run. NULL = never analyzed.';

-- Refresh the convenience view so it includes the new columns
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