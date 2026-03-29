ALTER TABLE recommendations
ADD COLUMN IF NOT EXISTS survival_probability NUMERIC;

ALTER TABLE recommendations
ADD COLUMN IF NOT EXISTS estimated_annual_revenue NUMERIC;

ALTER TABLE recommendations
ADD COLUMN IF NOT EXISTS capture_rate NUMERIC;
