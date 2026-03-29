ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS summary text;

COMMENT ON COLUMN recommendations.summary IS 'User-facing explanation; qualitative signals only. Internal scoring reasoning remains in recommendations.reasoning.';

CREATE OR REPLACE VIEW properties_with_top_rec AS
SELECT
    p.id,
    p.crexi_id,
    p.crexi_url,
    p.address,
    p.city,
    p.zip_code,
    p.latitude,
    p.longitude,
    p.square_footage,
    p.asking_rent_per_sqft,
    p.description,
    p.created_at,
    p.updated_at,
    p.restaurant_analysis,
    p.restaurant_analyzed_at,
    p.state_code,
    p.retail_analysis,
    p.retail_analyzed_at,
    p.foot_traffic_analysis,
    p.foot_traffic_analyzed_at,
    p.ml_predictions,
    r.business_type AS top_rec_business,
    r.score        AS top_rec_score,
    r.reasoning    AS top_rec_reasoning,
    r.summary      AS top_rec_summary
FROM properties p
LEFT JOIN LATERAL (
    SELECT business_type, score, reasoning, summary
    FROM recommendations
    WHERE property_id = p.id
    ORDER BY rank
    LIMIT 1
) r ON true;
